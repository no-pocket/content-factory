import pytest


@pytest.mark.parametrize('ending', ['E aqui está a demonstração completa.', 'Here is the complete demonstration.'])
def test_late_payoff_survives_context_budget_pt_en(ending):
    from app.editorial_context import build_candidate_context
    text = 'GTA VI análise ' * 100 + ending
    transcript = {'segments': [{'start': 0, 'end': 10, 'text': 'Antes'},
                               {'start': 10, 'end': 50, 'text': text},
                               {'start': 50, 'end': 60, 'text': 'Depois'}]}
    context = build_candidate_context({'candidates': [{'start': 10, 'end': 50}]}, 0, transcript)
    assert context['text'].endswith(ending)
    assert context['before'][0]['text'] == 'Antes'
    assert context['after'][0]['text'] == 'Depois'
    assert context['segments'][0]['segment_id'] == 1
    assert len(context['transcript_sha256']) == 64
    assert context['coverage']['complete_candidate'] is True


def test_title_zero_and_transcript_echo_rejected():
    from app.editorial_context import validate_title
    evidence = {'text': 'Vamos mostrar o novo mapa de GTA 6. O mapa revela Vice City.'}
    for title in ['0', '', 'Vamos mostrar o novo mapa', 'Rockstar confirma lançamento amanhã']:
        assert not validate_title(title, evidence)['valid']
    assert validate_title('Mapa de GTA 6 revela Vice City', evidence)['valid']


def test_prompt_budget_fails_explicitly_without_prefix_truncation():
    from app.editorial_context import require_prompt_budget
    with pytest.raises(ValueError, match='budget'):
        require_prompt_budget('x' * 5000, context_window=4096, reserve=450)
    result = require_prompt_budget('Complete ending.', context_window=4096, reserve=450)
    assert result['method'] == 'utf8_byte_upper_bound'


def test_heuristic_candidates_keep_complete_text():
    from app.core import propose_clips
    text = 'GTA VI ' * 150 + 'FINAL PAYOFF'
    clips = propose_clips([{'start': 0, 'end': 40, 'text': text}], 40)
    assert clips[0]['text'].endswith('FINAL PAYOFF')


def test_ranker_chunks_full_candidates_instead_of_truncating(monkeypatch):
    import io
    import json
    from app.ranker import rerank_with_ollama
    seen = []
    events = []
    def reply(request, **kwargs):
        prompt = json.loads(request.data)['prompt']
        seen.append(prompt)
        return io.BytesIO(json.dumps({'response': json.dumps({'ranked': [{'index': 0, 'reason': 'SYNTHETIC complete'}]}), 'done_reason': 'stop'}).encode())
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', reply)
    monkeypatch.setenv('OLLAMA_URL', 'http://localhost:11434')
    clips = [{'start': i*50, 'end': i*50+40, 'score': 10-i, 'text': ('word '*250)+f'PAYOFF_{i}', 'reason': 'synthetic'} for i in range(6)]
    selected = rerank_with_ollama(clips, count=3, on_event=lambda name, details: events.append((name, details)))
    assert len(selected) == 3
    assert len(seen) > 1
    assert any('PAYOFF_5' in prompt for prompt in seen)
    assert all(len(prompt.encode())+256+700 <= 8192 for prompt in seen)
    assert any(name == 'context_chunking' for name, _ in events)


def test_director_sees_ending_after_old_2200_limit(monkeypatch):
    import io
    import json
    from app.director import direct_edit
    prompts = []
    def reply(request, **kwargs):
        prompts.append(json.loads(request.data)['prompt'])
        return io.BytesIO(b'{"response":"{\\"hook\\":\\"\\",\\"effects\\":[],\\"broll\\":[]}","done_reason":"stop"}')
    monkeypatch.setenv('OLLAMA_URL', 'http://localhost:11434')
    monkeypatch.setattr('app.director.urllib.request.urlopen', reply)
    direct_edit({'start': 0, 'end': 40, 'text': 'a '*1120+'FINAL_PAYOFF'}, {}, mode='ollama')
    assert len(prompts) == 1
    assert 'FINAL_PAYOFF' in prompts[0]
