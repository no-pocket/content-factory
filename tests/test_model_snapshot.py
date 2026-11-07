import io
import json

from app import director, ranker


def test_explicit_model_is_used_instead_of_changed_environment(monkeypatch):
    seen = []
    monkeypatch.setenv('OLLAMA_MODEL', 'different-environment-model')
    monkeypatch.setenv('OLLAMA_URL', 'http://localhost:11434')
    def reply(request, **kwargs):
        payload = json.loads(request.data)
        seen.append(payload['model'])
        answer = {'clips': []} if 'SEGMENTOS:' in payload['prompt'] else {'hook': '', 'effects': [], 'broll': []}
        return io.BytesIO(json.dumps({'done_reason': 'stop', 'response': json.dumps(answer)}).encode())
    monkeypatch.setattr(ranker.urllib.request, 'urlopen', reply)
    ranker.propose_from_transcript([{'start': 0, 'end': 30, 'text': 'complete thought'}], 40,
                                  model='qwen2.5:1.5b')
    director.direct_edit({'start': 0, 'end': 30, 'text': 'complete thought'}, {},
                         mode='ollama', model='qwen2.5:1.5b')
    assert seen == ['qwen2.5:1.5b', 'qwen2.5:1.5b']
