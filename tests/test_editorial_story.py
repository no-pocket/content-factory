import pytest


def context(text, after=None):
    return {'text': text, 'source_range': {'start': 0, 'end': 30},
            'segments': [{'segment_id': 0, 'source_start': 0, 'source_end': 30, 'text': text}],
            'after': after or [], 'before': []}


def test_live_promotion_is_not_game_discovery():
    from app.editorial_story import assess_story
    result = assess_story(context('GTA VI na minha live. Inscreva-se no canal e deixe o like. Minha live começa agora.'), {}, None)
    assert result['relevance'] == 'SELF_PROMOTION_DOMINANT'
    assert result['content_grade'] is None
    assert result['quality_uncertain'] is True


@pytest.mark.parametrize('text', ['Agora vou mostrar', 'O jornalista falou que ele é', 'Now let me show you', 'Bom, tipo, sei lá.'])
def test_pause_before_demonstration_is_not_closure(text):
    from app.editorial_story import assess_story
    result = assess_story(context(text), {}, None)
    assert result['closure'] == 'INCOMPLETE'
    assert result['fallback_reason']


def test_extend_to_payoff_without_cutting_word():
    from app.editorial_story import assess_story, validate_story_boundary
    ctx = context('Agora vou mostrar', [{'segment_id': 1, 'source_start': 30, 'source_end': 38,
                                        'text': 'Aqui está o mapa completo.',
                                        'words': [{'source_start': 37, 'source_end': 38, 'text': 'completo.'}]}])
    result = assess_story(ctx, {'max_seconds': 60}, None)
    assert result['proposed_source_end'] == 38
    assert validate_story_boundary({'source_start': 0, 'source_end': 38}, ctx)['valid']
    with pytest.raises(ValueError):
        validate_story_boundary({'source_start': 0, 'source_end': 37.5}, ctx)


def test_invalid_model_evidence_falls_back_explicitly():
    from app.editorial_story import assess_story
    result = assess_story(context('Uma análise de GTA VI.'), {}, {'closure': 'COMPLETE', 'evidence': [{'segment_id': 99, 'quote': 'inexistent'}]})
    assert result['closure'] == 'UNCERTAIN'
    assert result['quality_uncertain']
    assert result['fallback_reason'] == 'invalid_model_evidence'


def test_duration_limit_does_not_claim_promised_payoff():
    from app.editorial_story import assess_story
    ctx = context('Vou mostrar', [{'segment_id': 1, 'source_start': 30, 'source_end': 75, 'text': 'Aqui está a prova.'}])
    result = assess_story(ctx, {'max_seconds': 60}, None)
    assert result['closure'] == 'INCOMPLETE'
    assert result['proposed_source_end'] is None


def test_annotation_preserves_word_times_and_penalizes_promotion():
    from app.editorial_story import annotate_candidates
    clips = [{'start': 0, 'end': 20, 'text': 'old'}, {'start': 30, 'end': 50, 'text': 'old'}]
    segments = [{'start': 0, 'end': 20, 'text': 'Minha live. Meu canal. Inscreva-se.',
                 'words': [{'start': 0, 'end': 1, 'text': 'Minha'}]},
                {'start': 30, 'end': 50, 'text': 'Uma análise de GTA VI com informação.'}]
    annotated = annotate_candidates(clips, segments)
    assert annotated[0]['start'] == 30
    assert annotated[1]['editorial_penalty'] > annotated[0]['editorial_penalty']
    assert annotated[1]['editorial_context']['segments'][0]['words'][0]['source_end'] == 1
    assert clips[0]['text'] == 'old'

def test_annotation_completes_sentence_across_whisper_segment_boundary():
    from app.editorial_story import annotate_candidates
    segments = [
        {'start': 0, 'end': 30, 'text': 'A free gift with any purchase from the',
         'words': [{'start': 29, 'end': 30, 'word': 'the'}]},
        {'start': 30, 'end': 38, 'text': 'Rockstar store, which is incredible. This is next.',
         'words': [{'start': 30, 'end': 31, 'word': 'Rockstar'},
                   {'start': 31, 'end': 32, 'word': 'store,'},
                   {'start': 32, 'end': 33, 'word': 'which'},
                   {'start': 33, 'end': 34, 'word': 'is'},
                   {'start': 34, 'end': 35, 'word': 'incredible.'},
                   {'start': 36, 'end': 38, 'word': 'This is next.'}]}]
    clip = annotate_candidates([{'start': 0, 'end': 30}], segments)[0]
    assert clip['end'] == pytest.approx(35.15)
    assert clip['story_assessment']['boundary_adjusted']
    assert clip['story_assessment']['closure'] != 'COMPLETE'


def test_annotation_preserves_last_word_and_available_speech_tail():
    from app.editorial_story import annotate_candidates
    segments = [{'start': 0, 'end': 20.08, 'text': 'The conclusion.',
                 'words': [{'start': 19, 'end': 20.08, 'word': 'conclusion.'}]},
                {'start': 22, 'end': 25, 'text': 'Next topic.'}]
    clip = annotate_candidates([{'start': 0, 'end': 20}], segments)[0]
    assert clip['end'] == pytest.approx(20.23)
    assert clip['baseline_window']['end'] == 20


def test_unresolved_boundary_is_explicit_and_does_not_extend_beyond_budget():
    from app.editorial_story import annotate_candidates
    segments = [{'start': 0, 'end': 30, 'text': 'A purchase from the'},
                {'start': 30, 'end': 70, 'text': 'store.'}]
    clip = annotate_candidates([{'start': 0, 'end': 30}], segments, max_seconds=35)[0]
    assert clip['end'] == 30
    assert clip['story_assessment']['closure'] == 'INCOMPLETE'
    assert clip['story_assessment']['boundary_reason'] == 'no_complete_sentence_within_observed_budget'


def test_candidate_text_excludes_following_words_from_overlapping_segment():
    from app.editorial_context import build_candidate_context
    segments = [{'start': 0, 'end': 10, 'text': 'Finished. Unseen promise.',
                 'words': [{'start': 0, 'end': 4, 'word': 'Finished.'},
                           {'start': 6, 'end': 10, 'word': 'Unseen promise.'}]}]
    ctx = build_candidate_context({'candidates': [{'start': 0, 'end': 4.15}]}, 0, {'segments': segments})
    assert ctx['text'] == 'Finished.'


def test_model_cannot_claim_complete_using_early_quote_in_long_final_segment():
    from app.editorial_story import assess_story
    result = assess_story(context('The map is huge. A purchase from the'), {},
                          {'closure': 'COMPLETE', 'evidence': [{'segment_id': 0, 'quote': 'The map is huge.'}]})
    assert result['closure'] != 'COMPLETE'
    assert result['fallback_reason'] == 'invalid_model_evidence'


def test_model_complete_does_not_override_source_word_truncation():
    from app.editorial_story import assess_story
    ctx = context('A conclusion.')
    ctx['segments'][0]['words'] = [{'source_start': 29, 'source_end': 30.2, 'text': 'conclusion.'}]
    result = assess_story(ctx, {}, {'closure': 'COMPLETE',
                                  'evidence': [{'segment_id': 0, 'quote': 'A conclusion.'}]})
    assert result['closure'] != 'COMPLETE'
    assert result['fallback_reason'] == 'invalid_model_evidence'


def test_revision_planner_rebuilds_captions_without_mutating_reviewed_candidate():
    import copy
    from app.editorial_story import prepare_source_end_revision
    job = {'settings': {'max_seconds': 60}, 'feedback_events': [{'event_id': 'human-review'}],
           'candidates': [{'start': 0, 'end': 20, 'candidate_id': 'original',
                           'artifact_id': 'sha256:old', 'render_revision': 1}]}
    original = copy.deepcopy(job)
    transcript = {'segments': [{'start': 0, 'end': 20.08, 'text': 'Conclusion.',
                               'words': [{'start': 19, 'end': 20.08, 'word': 'Conclusion.'}]},
                              {'start': 22, 'end': 25, 'text': 'Next.'}]}
    plan = prepare_source_end_revision(job, 0, transcript)
    assert job == original
    assert plan['parent_artifact_id'] == 'sha256:old'
    assert plan['clip']['end'] == pytest.approx(20.23)
    assert plan['clip']['timeline']['layers']['captions'][-1]['end'] == 20.08
    assert plan['clip']['timeline']['source_range']['end'] == pytest.approx(20.23)
    assert 'artifact_id' not in plan['clip']
    assert 'feedback_events' not in plan['clip']


def test_revision_planner_preserves_human_title_and_origin_unless_overridden():
    from app.editorial_story import prepare_source_end_revision
    job = {'settings': {'max_seconds': 60}, 'candidates': [
        {'start': 0, 'end': 20, 'timeline': {'layers': {'text': [
            {'text': 'Título humano aprovado', 'origin': 'human'}]}}}]}
    transcript = {'segments': [{'start': 0, 'end': 20, 'text': 'Conclusion.'},
                              {'start': 22, 'end': 25, 'text': 'Next.'}]}
    kept = prepare_source_end_revision(job, 0, transcript)['clip']['timeline']['layers']['text'][0]
    assert kept['text'] == 'Título humano aprovado'
    assert kept['origin'] == 'human'
    changed = prepare_source_end_revision(job, 0, transcript, editorial_title='Novo título')['clip']['timeline']['layers']['text'][0]
    assert changed['text'] == 'Novo título'
    assert changed['origin'] == 'human'

@pytest.mark.parametrize('text', [
    'Vou mostrar o mapa. Ele tem detalhes interessantes.',
    'I will show the map. This game has many details.',
    'Por que o mapa mudou?', 'Why did the map change?'])
def test_unresolved_narrative_obligation_survives_sentence_end(text):
    from app.editorial_story import assess_story
    result = assess_story(context(text), {}, {'closure': 'COMPLETE', 'evidence': [{'segment_id': 0, 'quote': text}]})
    assert result['closure'] == ('UNCERTAIN' if text.endswith('?') else 'INCOMPLETE')
    assert result['narrative']['open_obligations']


def test_payoff_must_match_promised_subject():
    from app.editorial_story import assess_story
    ctx = context('Vou mostrar o mapa.', [
        {'segment_id': 1, 'source_start': 30, 'source_end': 35, 'text': 'Aqui está meu teclado.'},
        {'segment_id': 2, 'source_start': 35, 'source_end': 40, 'text': 'Aqui está o mapa completo.'}])
    result = assess_story(ctx, {'max_seconds': 60}, None)
    assert result['proposed_source_end'] == 40


def test_do_not_extend_through_new_topic_or_promotion():
    from app.editorial_story import assess_story
    for transition in ('Mudando de assunto.', 'Subscribe to my channel.'):
        ctx = context('I will show the map.', [
            {'segment_id': 1, 'source_start': 30, 'source_end': 35, 'text': transition},
            {'segment_id': 2, 'source_start': 35, 'source_end': 40, 'text': 'Here is the map.'}])
        assert assess_story(ctx, {'max_seconds': 60}, None)['proposed_source_end'] is None


@pytest.mark.parametrize('text', ['Vou mostrar o mapa. Aqui está o mapa completo.',
                                 'I will show the map. Here is the complete map.',
                                 'Por que o mapa mudou? Porque o mapa ganhou uma ilha.',
                                 'Why did the map change? Because the map gained an island.',
                                 'This is the final map. Peace out.'])
def test_observed_resolution_is_not_automatic_semantic_approval(text):
    from app.editorial_story import assess_story
    result = assess_story(context(text), {}, None)
    assert result['closure'] == 'UNCERTAIN'
    assert not result['narrative']['open_obligations']
    assert result['human_ratings'] is None


def test_annotation_extends_past_punctuated_promise_to_related_payoff():
    from app.editorial_story import annotate_candidates
    segments = [{'start': 0, 'end': 30, 'text': 'Vou mostrar o mapa.'},
                {'start': 30, 'end': 35, 'text': 'Aqui está o mapa completo.'},
                {'start': 36, 'end': 40, 'text': 'Outro assunto.'}]
    clip = annotate_candidates([{'start': 0, 'end': 30}], segments)[0]
    assert clip['end'] == pytest.approx(35.15)
    assert clip['story_assessment']['closure'] == 'UNCERTAIN'


def test_revision_planner_can_repair_punctuated_unresolved_promise():
    from app.editorial_story import prepare_source_end_revision
    job = {'settings': {'max_seconds': 60}, 'candidates': [{'start': 0, 'end': 30}]}
    transcript = {'segments': [{'start': 0, 'end': 30, 'text': 'I will show the map.'},
                               {'start': 30, 'end': 35, 'text': 'Here is the complete map.'}]}
    result = prepare_source_end_revision(job, 0, transcript)
    assert result['clip']['end'] == 35

@pytest.mark.parametrize('text', ['Não vou mostrar o mapa.', 'I will not show the map.', 'Peace out. Right?'])
def test_non_commitment_or_rhetorical_tag_does_not_create_hard_veto(text):
    from app.editorial_story import assess_story
    assert assess_story(context(text), {}, None)['closure'] == 'UNCERTAIN'


def test_unrelated_because_answer_does_not_resolve_question():
    from app.editorial_story import assess_story
    result = assess_story(context('Why did the map change? Because my keyboard broke.'), {}, None)
    assert result['closure'] == 'UNCERTAIN'
    assert result['narrative']['open_obligations']

@pytest.mark.parametrize('text', ["What's up guys?", 'Como é que tá ansiedade?',
                                 'Como por exemplo, o jogo foi anunciado, né?', 'Why is it big, right?'])
def test_greetings_and_question_tags_are_not_unanswered_content_questions(text):
    from app.editorial_story import assess_story
    assert not assess_story(context(text), {}, None)['narrative']['open_obligations']


def test_narrative_observation_never_borrows_unheard_overlapping_sentence():
    from app.editorial_context import build_candidate_context
    from app.editorial_story import assess_story
    transcript = {'segments': [{'start': 0, 'end': 10, 'text': 'The map. I will show the proof.',
                               'words': [{'start': 0, 'end': 4, 'word': 'The map.'},
                                         {'start': 6, 'end': 10, 'word': 'I will show the proof.'}]}]}
    ctx = build_candidate_context({'candidates': [{'start': 0, 'end': 4.15}]}, 0, transcript)
    result = assess_story(ctx, {}, None)
    assert not result['narrative']['open_obligations']


def test_question_with_possible_implicit_answer_stays_uncertain_without_hard_rejection():
    from app.editorial_story import assess_story, safe_source_end
    ctx = context('Por que a Lucía está nesta imagem? Isso aqui é Flashback de guerra do Jason.')
    result = assess_story(ctx, {}, None)
    assert result['closure'] == 'UNCERTAIN'
    assert result['narrative']['open_obligations']
    assert not result['narrative']['blocking_obligations']
    model = {'closure': 'COMPLETE', 'evidence': [{'segment_id': 0, 'quote': ctx['text']}]}
    assert assess_story(ctx, {}, model)['closure'] == 'UNCERTAIN'
    assert safe_source_end(ctx, max_seconds=60)['resolved']

@pytest.mark.parametrize('text', ['I will show the map. Here is not the map.',
                                 'Vou mostrar o mapa. Aqui não está o mapa.',
                                 'I will show the map. Here is definitely not the map.'])
def test_explicit_negation_is_not_evidence_of_promised_payoff(text):
    from app.editorial_story import assess_story
    model = {'closure': 'COMPLETE', 'evidence': [{'segment_id': 0, 'quote': text}]}
    result = assess_story(context(text), {}, model)
    assert result['closure'] == 'INCOMPLETE'
    assert result['narrative']['blocking_obligations']
