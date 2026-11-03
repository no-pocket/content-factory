import json
import urllib.error
from app.ranker import rerank_with_ollama


def sample():
    return [dict(start=i*50.0,end=i*50.0+40,score=10-i,text=f'Video trecho {i}',reason='base') for i in range(5)]


def test_ollama_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.URLError('offline')
    monkeypatch.setattr('app.ranker.urllib.request.urlopen', fail)
    assert len(rerank_with_ollama(sample())) == 3


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
