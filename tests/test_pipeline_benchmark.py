"""Synthetic responses exercise benchmark bookkeeping, never editorial quality."""
import io
import json

from research import evaluate_sprint as evaluation


def test_pipeline_benchmark_covers_actual_three_tasks_and_validated_text(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation, 'JOBS', tmp_path)
    monkeypatch.setenv('OLLAMA_URL', 'http://localhost:11434')
    segments = [{'start': n*6, 'end': (n+1)*6, 'text': 'Synthetic English speech about GTA, complete thought.', 'words': []}
                for n in range(120)]
    (tmp_path / 'synthetic.transcript.json').write_text(json.dumps({'language': 'en', 'segments': segments}))
    def reply(request, **kwargs):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith('/api/tags'):
            body = {'models': [{'name': 'qwen2.5:1.5b'}, {'name': 'qwen2.5:3b'}]}
        elif url.endswith('/api/ps'):
            body = {'models': []}
        else:
            prompt = json.loads(request.data)['prompt']
            if 'SEGMENTOS:' in prompt:
                result = {'clips': [{'start_segment': 0, 'end_segment': 3, 'reason': 'Synthetic fixture'}]}
            elif 'CANDIDATOS:' in prompt:
                result = {'ranked': [{'index': n, 'reason': 'Synthetic fixture'} for n in range(3)]}
            else:
                result = {'hook': 'English speech Synthetic', 'effects': [], 'broll': []}
            body = {'response': json.dumps(result), 'done_reason': 'stop', 'prompt_eval_count': 100, 'eval_count': 50}
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(evaluation.urllib.request, 'urlopen', reply)
    report = evaluation.pipeline_models({'id': 'synthetic', 'duration': 720, 'language': 'en'})
    assert report['language'] == 'en'
    assert len(report['runs']) == 4
    for result in report['runs']:
        assert {c['task'] for c in result['calls']} == {'proposal', 'rerank', 'director'}
        assert len(result['reranked']) == 3
        assert result['validated_text_layers'][0]['text'] == 'English speech Synthetic'
