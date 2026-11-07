import json
import urllib.error
from app.ranker import rerank_with_ollama, propose_from_transcript, select_highlights


def sample():
    return [dict(start=i*50.0,end=i*50.0+40,score=10-i,text=f'Video trecho {i}',reason='base') for i in range(5)]


def test_gpu_backend_routes_ranker_to_kepler(monkeypatch):
    seen = []
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"response":"{\\"ranked\\":[{\\"index\\":0}]}"}'
    def open_request(request, timeout):
        seen.append(request.full_url)
        return Reply()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', open_request)
    rerank_with_ollama(sample(), backend='kepler_gpu')
    assert seen == ['http://kepler-bridge:11434/api/generate']


def test_ollama_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.URLError('offline')
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', fail)
    assert len(rerank_with_ollama(sample())) == 3


def test_semantically_invalid_proposals_record_rejection_reasons(monkeypatch):
    import io
    reply = {'response': json.dumps({'clips': [{'start_segment': 0, 'end_segment': 3, 'reason': 'Synthetic too long'}]}),
             'done_reason': 'stop'}
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: io.BytesIO(json.dumps(reply).encode()))
    events = []
    segments = [{'start': n*30, 'end': (n+1)*30, 'text': 'Synthetic English speech'} for n in range(4)]
    assert propose_from_transcript(segments, 120, on_event=lambda event, details: events.append((event, details))) == []
    assert events[-1][0] == 'proposal_chunk_rejected'
    assert events[-1][1]['rejections'] == {'duration': 1}


def test_ranker_rejects_valid_json_cut_off_by_token_limit(monkeypatch):
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': '{"ranked":[{"index":3}]}',
                               'done_reason': 'length'}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    events = []
    result = rerank_with_ollama(sample(), count=2, on_event=lambda name, details: events.append(name))
    assert [x['start'] for x in result] == [0, 50]
    assert events[-1] == 'fallback'


def test_transcript_proposal_rejects_truncated_prompt(monkeypatch):
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': '{"clips":[]}', 'prompt_truncated': True}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    events = []
    segments = [{'start': 0, 'end': 20, 'text': 'GTA VI'}]
    assert propose_from_transcript(segments, 20, on_event=lambda name, details: events.append(name)) == []
    assert events[-1] == 'proposal_chunk_failed'


def test_ollama_reorders(monkeypatch):
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': json.dumps({'ranked': [{'index': 3, 'reason': 'Boa surpresa'}, {'index': 0, 'reason': 'Contexto'}]})}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    result = rerank_with_ollama(sample(), count=2)
    assert {x['start'] for x in result} == {150, 0}
    assert any(x.get('ai_reason') == 'Boa surpresa' for x in result)


def test_ollama_invalid_indices(monkeypatch):
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps({'response': json.dumps({'ranked':[{'index':999}]})}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    assert len(rerank_with_ollama(sample())) == 3


def test_ollama_emits_real_events(monkeypatch):
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': json.dumps({'ranked': [{'index': 1, 'reason': 'Claro'}]})}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    events = []
    rerank_with_ollama(sample(), count=2, on_event=lambda name, data: events.append((name, data)))
    assert [x[0] for x in events] == ['analyzing', 'completed']
    assert events[0][1]['total_candidates'] == 5


def test_ollama_emits_fallback_event(monkeypatch):
    import urllib.error
    def fail(*args, **kwargs):
        raise urllib.error.URLError('offline')
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', fail)
    events = []
    rerank_with_ollama(sample(), on_event=lambda name, data: events.append((name, data)))
    assert [x[0] for x in events] == ['analyzing', 'fallback']
    assert 'offline' in events[-1][1]['reason']


def test_transcript_proposals_can_find_windows_outside_heuristic_shortlist(monkeypatch):
    segments = [
        {'start': i * 10.0, 'end': i * 10.0 + 9, 'text': f'contexto {i} com uma ideia completa'}
        for i in range(12)
    ]
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': json.dumps({'clips': [
                {'start_segment': 8, 'end_segment': 11, 'reason': 'Conclusão forte'}
            ]})}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    proposals = propose_from_transcript(segments, 120)
    assert len(proposals) == 1
    assert proposals[0]['start'] == 80
    assert proposals[0]['end'] == 119
    assert proposals[0]['text'].startswith('contexto 8')


def test_transcript_proposals_reject_invalid_or_too_short_spans(monkeypatch):
    segments = [{'start': i * 10.0, 'end': i * 10.0 + 9, 'text': f'fala {i}'} for i in range(7)]
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'response': json.dumps({'clips': [
                {'start_segment': 0, 'end_segment': 0},
                {'start_segment': -1, 'end_segment': 3},
                {'start_segment': 0, 'end_segment': 6},
                {'start_segment': 2, 'end_segment': 5},
            ]})}).encode()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', lambda *a, **k: Reply())
    proposals = propose_from_transcript(segments, 70)
    assert [(p['start'], p['end']) for p in proposals] == [(20, 59)]


def test_selection_combines_transcript_discovery_with_heuristics(monkeypatch):
    segments = [{'start': i * 10.0, 'end': i * 10.0 + 9,
                 'text': f'contexto {i} com conclusão independente'} for i in range(12)]
    def response(request, timeout):
        payload = json.loads(request.data)
        answer = ({'clips': [{'start_segment': 8, 'end_segment': 11, 'reason': 'final forte'}]}
                  if 'SEGMENTOS:' in payload['prompt'] else
                  {'ranked': [{'index': 0, 'reason': 'final forte'}]})
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({'response': json.dumps(answer)}).encode()
        return Reply()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', response)
    selected = select_highlights(segments, 120, count=3)
    assert any(c['start'] == 80 and c['proposal_source'] == 'transcript' for c in selected)


def test_ranker_includes_discovered_clip_even_when_heuristic_scores_are_higher(monkeypatch):
    candidates = [dict(start=i * 70, end=i * 70 + 40, score=100 - i,
                       text=f'heuristic {i}', reason='keyword') for i in range(14)]
    candidates.append(dict(start=1100, end=1140, score=5, text='independent payoff',
                           reason='model', proposal_source='transcript'))
    seen = []
    def response(request, timeout):
        brief = json.loads(request.data)['prompt']
        seen.append(brief)
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({'response': json.dumps({'ranked': [{'index': 0, 'reason': 'payoff'}]})}).encode()
        return Reply()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', response)
    rerank_with_ollama(candidates, count=1)
    assert 'independent payoff' in seen[0]


def test_transcript_discovery_samples_entire_long_video_with_bounded_calls(monkeypatch):
    segments = [{'start': i * 10.0, 'end': i * 10.0 + 9, 'text': f'segmento {i}'} for i in range(500)]
    seen = []
    def response(request, timeout):
        seen.append(json.loads(request.data)['prompt'])
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"response":"{\\"clips\\":[]}"}'
        return Reply()
    monkeypatch.setenv('OLLAMA_PROPOSAL_MAX_CHUNKS', '4')
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', response)
    propose_from_transcript(segments, 5000)
    assert len(seen) == 4
    assert 'segmento 0' in seen[0]
    assert 'segmento 499' in seen[-1]


def test_transcript_proposal_respects_configured_duration_and_chunk_limit(monkeypatch):
    segments = [{'start': i * 10.0, 'end': i * 10.0 + 9, 'text': f'fala {i}'} for i in range(100)]
    calls = []
    def response(request, timeout):
        calls.append(timeout)
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({'response': json.dumps({'clips': [
                    {'start_segment': 0, 'end_segment': 1, 'reason': 'curto'}
                ]})}).encode()
        return Reply()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', response)
    proposals = propose_from_transcript(segments, 1000, max_chunks=2, timeout=42,
                                        min_seconds=10, max_seconds=30)
    assert len(calls) == 2
    assert calls == [42, 42]
    assert len(proposals) == 2
    assert all(p['end'] - p['start'] == 19 for p in proposals)


def test_ranker_respects_configured_shortlist_and_timeout(monkeypatch):
    calls = []
    def response(request, timeout):
        calls.append((json.loads(request.data)['prompt'], timeout))
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"response":"{\\"ranked\\":[{\\"index\\":0}]}"}'
        return Reply()
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', response)
    rerank_with_ollama(sample(), count=1, shortlist_limit=2, timeout=41)
    assert calls[0][0].count('"transcript"') == 2
    assert calls[0][1] == 41
