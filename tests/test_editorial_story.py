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
