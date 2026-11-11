import json

from app import social_captions


def test_model_output_is_source_anchored_and_varies_by_destination():
    def model(prompt, settings):
        return {'response': json.dumps({'quote': 'O jogo vai chegar em 2027.'}), 'done_reason': 'stop'}
    clip = {'text': 'O jogo vai chegar em 2027. Veja a explicação.'}
    results = social_captions.generate(clip, {'llm_backend': 'ollama'}, 'pt', infer=model)
    assert results['instagram']['origin'] == 'ollama'
    assert 'O jogo vai chegar em 2027.' in results['instagram']['text']
    assert results['instagram']['text'] != results['facebook']['text']


def test_unsupported_model_hook_is_not_used(monkeypatch):
    clip={'text':'O jogo vai chegar em 2027.'}
    model=lambda *_: {'response':json.dumps({'quote':'O jogo vai chegar em 2027.','hook':'Lançamento confirmado amanhã!'}),'done_reason':'stop'}
    result=social_captions.generate(clip, {'llm_backend':'ollama'}, 'pt', infer=model)
    assert 'amanhã' not in result['instagram']['text']
    assert result['instagram']['reason']=='hook_not_grounded'
    assert result['instagram']['origin']=='ollama'


def test_model_hook_is_used_only_if_anchored_to_the_source():
    clip={'text':'A Rockstar revelou imagens do mapa de Vice City.'}
    model=lambda *_: {'response':json.dumps({'quote':clip['text'],'hook':'Imagens do mapa de Vice City'}),'done_reason':'stop'}
    result=social_captions.generate(clip, {'llm_backend':'ollama'}, 'pt', infer=model)
    assert result['instagram']['text'].startswith('🔥 Imagens do mapa de Vice City')


def test_quote_cannot_drop_negation_from_source_sentence():
    clip={'text':'O jogo não vai chegar em 2027.'}
    model=lambda *_: {'response':json.dumps({'quote':'vai chegar em 2027.'}),'done_reason':'stop'}
    result=social_captions.generate(clip, {'llm_backend':'ollama'}, 'pt', infer=model)
    assert result['instagram']['origin']=='fallback'
    assert 'não vai chegar' in result['instagram']['text']


def test_suggestions_use_only_words_in_rendered_timeline():
    clip={'text':'Trecho cortado que não aparece. Trecho efetivamente ouvido.',
          'timeline':{'layers':{'captions':[{'text':'Trecho'}, {'text':'efetivamente'}, {'text':'ouvido.'}]}}}
    result=social_captions.generate(clip, {'llm_backend':'external'}, 'pt', infer=lambda *_: None)
    assert 'Trecho efetivamente ouvido.' in result['instagram']['text']
    assert 'cortado' not in result['instagram']['text']


def test_missing_timeline_captions_do_not_fall_back_to_unheard_text():
    clip={'text':'Texto potencialmente removido.','timeline':{'layers':{}}}
    result=social_captions.generate(clip, {'llm_backend':'ollama'}, 'pt', infer=lambda *_: None)
    assert result['instagram']['text']==''
    assert result['instagram']['reason']=='transcript_missing'


def test_invented_or_truncated_model_reply_falls_back_to_actual_transcript():
    clip = {'text': 'O jogo vai chegar em 2027.'}
    for reply in ({'response': '{"quote":"Data confirmada!"}', 'done_reason': 'stop'},
                  {'response': '{"quote":"O jogo vai chegar em 2027."}', 'done_reason': 'length'}):
        result = social_captions.generate(clip, {'llm_backend': 'ollama'}, 'pt', infer=lambda *_: reply)
        assert result['instagram']['origin'] == 'fallback'
        assert result['instagram']['reason']
        assert 'O jogo vai chegar em 2027.' in result['instagram']['text']
        assert 'Data confirmada' not in result['instagram']['text']


def test_missing_transcript_does_not_invent_caption():
    result = social_captions.generate({}, {'llm_backend': 'ollama'}, 'pt', infer=lambda *_: None)
    assert result['instagram']['text'] == ''
    assert result['instagram']['reason'] == 'transcript_missing'


def test_unknown_language_does_not_inject_portuguese_or_english():
    result=social_captions.generate({'text':'La noticia es importante.'},{'llm_backend':'external'},'es',infer=lambda *_: None)
    assert 'O que você acha?' not in result['instagram']['text']
    assert 'What do you think?' not in result['instagram']['text']


def test_local_model_failure_is_diagnosed_without_exposing_exception_text():
    def failing(*args):
        raise OSError('SECRET not to be logged')
    result=social_captions.generate({'text':'Texto de fonte autorizada.'},{'llm_backend':'ollama'},'pt',infer=failing)
    assert result['instagram']['reason']=='local_model_unavailable'
    assert 'SECRET' not in str(result)


def test_local_model_redirects_are_rejected():
    import pytest
    with pytest.raises(ValueError, match='redirect'):
        social_captions._NoRedirect().redirect_request(None, None, None, None, None, None)


def test_local_model_response_size_is_bounded(monkeypatch):
    import pytest
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, size): return b'x' * size
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(social_captions.urllib.request, 'build_opener', lambda *args: Opener())
    with pytest.raises(ValueError, match='response too large'):
        social_captions._infer('prompt', {'llm_backend':'ollama'})


def test_existing_suggestions_are_preserved_when_job_resumes(monkeypatch):
    prior = {'instagram': {'text': 'Legenda revisada', 'origin': 'human', 'reason': None}}
    clip = {'text': 'Conteúdo original.', 'social_captions': prior}
    monkeypatch.setattr(social_captions, 'generate', lambda *a, **k: (_ for _ in ()).throw(AssertionError('should not regenerate')))
    social_captions.ensure(clip, {'llm_backend': 'ollama'}, 'pt')
    assert clip['social_captions'] == prior


def test_regeneration_preserves_review_and_rejects_stale_artifacts(v2job, monkeypatch):
    from app import service, store
    from test_editorial_service_v2 import review_request
    cid = v2job['candidates'][0]['candidate_id']
    v2job['candidates'][0]['text'] = 'O jogo vai chegar em 2027.'
    store.save(v2job)
    service.review_candidate_v2(v2job['id'], cid, review_request(v2job))
    before = store.load(v2job['id'])
    monkeypatch.setattr(social_captions, 'generate', lambda *a, **k: {'instagram': {'text': 'Rascunho', 'origin': 'fallback', 'reason': 'test'}})
    result = social_captions.regenerate(v2job['id'], cid, before['candidates'][0]['artifact_id'])
    after = store.load(v2job['id'])
    assert result['instagram']['text'] == 'Rascunho'
    assert after['feedback_events'] == before['feedback_events']
    assert after['candidates'][0]['artifact_id'] == before['candidates'][0]['artifact_id']
    import pytest
    with pytest.raises(service.Conflict):
        social_captions.regenerate(v2job['id'], cid, 'sha256:' + '0'*64)


def test_regeneration_does_not_overwrite_newer_caption(v2job, monkeypatch):
    import pytest
    from app import service, store
    cid=v2job['candidates'][0]['candidate_id']
    def concurrent(*args, **kwargs):
        job=store.load(v2job['id'])
        job['candidates'][0]['social_captions']={'instagram':{'text':'Nova edição'}}
        store.save(job)
        return {'instagram':{'text':'Resposta atrasada'}}
    monkeypatch.setattr(social_captions,'generate',concurrent)
    with pytest.raises(service.Conflict):
        social_captions.regenerate(v2job['id'],cid,v2job['candidates'][0]['artifact_id'])
    assert store.load(v2job['id'])['candidates'][0]['social_captions']['instagram']['text']=='Nova edição'


def test_legacy_candidate_can_get_suggestion_without_new_approval(v2job, monkeypatch):
    from app import service, store
    from app.editorial_contracts import candidate_key
    job=store.load(v2job['id'])
    job['editorial_protocol']=1
    job['candidates'][0].pop('artifact_id', None)
    job['candidates'][0]['text']='Trecho antigo autorizado.'
    store.save(job)
    cid=candidate_key(job['id'],0)
    monkeypatch.setattr(social_captions,'generate',lambda *a, **k: {'instagram':{'text':'Sugestão legada','origin':'fallback','reason':None}})
    result=social_captions.regenerate(job['id'],cid,None)
    assert result['instagram']['text']=='Sugestão legada'
    assert not store.load(job['id']).get('feedback_events')


def test_new_render_does_not_reuse_old_suggestion(v2job):
    from app.artifacts import register_render
    job=v2job
    clip=job['candidates'][0]
    old_artifact=clip['artifact_id']
    clip['social_captions']={'instagram':{'text':'Legenda do render anterior'}}
    register_render(job,0)
    assert 'social_captions' not in clip
    assert clip['social_caption_history'][-1]['artifact_id']==old_artifact


from test_editorial_service_v2 import v2job


def test_caption_edit_keys_are_isolated_by_candidate_artifact_and_platform():
    from app.publication_calendar import caption_key
    assert caption_key('job', 'a', 'hash1', 'instagram') != caption_key('job', 'a', 'hash1', 'facebook')
    assert caption_key('job', 'a', 'hash1', 'instagram') != caption_key('job', 'b', 'hash1', 'instagram')
    assert caption_key('job', 'a', 'hash1', 'instagram') != caption_key('job', 'a', 'hash2', 'instagram')
