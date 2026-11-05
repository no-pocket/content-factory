import json

import pytest

from app.kepler_bridge import (resolve_model_blob, translate_generate, translate_reply,
                               check_context_budget, qwen_chat_prompt, preflight_context)


def test_resolves_existing_ollama_model_without_hardcoded_digest(tmp_path):
    manifest = tmp_path / 'manifests' / 'registry.ollama.ai' / 'library' / 'qwen2.5' / '3b'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'layers': [{'mediaType': 'application/vnd.ollama.image.model',
                                               'digest': 'sha256:abc123'}]}))
    blob = tmp_path / 'blobs' / 'sha256-abc123'
    blob.parent.mkdir()
    blob.write_bytes(b'model')
    assert resolve_model_blob(tmp_path, 'qwen2.5:3b') == blob


def test_rejects_model_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        resolve_model_blob(tmp_path, '../secret:3b')


def test_translates_ollama_json_request_to_llama_chat():
    schema = {'type': 'object', 'properties': {'hook': {'type': 'string'}}}
    request = translate_generate({'model': 'qwen2.5:3b', 'prompt': 'Escolha cortes', 'stream': False,
                                  'format': schema, 'options': {'temperature': 0, 'num_predict': 75}},
                                 model='qwen2.5:3b')
    assert request['messages'] == [{'role': 'user', 'content': 'Escolha cortes'}]
    assert request['max_tokens'] == 75
    assert request['response_format'] == {'type': 'json_object', 'schema': schema}


def test_bridge_preserves_response_and_timings():
    reply = translate_reply({'choices': [{'message': {'content': '{"clips":[]}'}}],
                             'usage': {'prompt_tokens': 30, 'completion_tokens': 8},
                             'timings': {'prompt_ms': 900, 'predicted_ms': 300}}, 'qwen2.5:3b')
    assert reply['response'] == '{"clips":[]}'
    assert reply['prompt_eval_count'] == 30
    assert reply['eval_count'] == 8
    assert reply['prompt_eval_duration'] == 900_000_000


def test_bridge_rejects_another_model():
    with pytest.raises(ValueError):
        translate_generate({'model': 'other:3b', 'prompt': 'hi'}, model='qwen2.5:3b')


def test_gpu_context_budget_includes_chat_template_and_reserved_output():
    prompt = qwen_chat_prompt('Ola mundo')
    assert prompt == '<|im_start|>user\nOla mundo<|im_end|>\n<|im_start|>assistant\n'
    assert check_context_budget(3000, 700, 4096, margin=16) == 4096
    with pytest.raises(ValueError, match='context'):
        check_context_budget(3500, 700, 4096, margin=16)
    with pytest.raises(ValueError, match='8192'):
        check_context_budget(100, 50, 4096, requested_context=8192)


def test_bridge_rejects_options_it_cannot_translate():
    with pytest.raises(ValueError, match='Unsupported'):
        translate_generate({'model': 'qwen2.5:3b', 'prompt': 'x',
                            'options': {'num_gpu': 99}}, model='qwen2.5:3b')


def test_bridge_marks_token_limit_and_prompt_truncation():
    reply = translate_reply({'choices': [{'message': {'content': '{"clips":[]}'},
                                         'finish_reason': 'length'}],
                             'usage': {'prompt_tokens': 25, 'completion_tokens': 2}},
                            'qwen2.5:3b', expected_prompt_tokens=30, context_window=4096)
    assert reply['done_reason'] == 'prompt_truncated'
    assert reply['prompt_truncated'] is True
    assert reply['context_window'] == 4096
    complete_prompt = translate_reply({'choices': [{'message': {'content': 'x'},
                                                    'finish_reason': 'length'}],
                                        'usage': {'prompt_tokens': 30, 'completion_tokens': 2}},
                                       'qwen2.5:3b', expected_prompt_tokens=30)
    assert complete_prompt['done_reason'] == 'length'


def test_preflight_counts_full_chat_prompt_with_live_model_tokenizer(monkeypatch):
    from io import BytesIO
    seen = []
    def open_request(request, timeout):
        url = request if isinstance(request, str) else request.full_url
        seen.append(url)
        if url.endswith('/props'):
            return BytesIO(json.dumps({'default_generation_settings': {'n_ctx': 4096},
                                       'chat_template': '<|im_start|>user<|im_end|>'}).encode())
        assert json.loads(request.data)['content'] == qwen_chat_prompt('Ola')
        return BytesIO(json.dumps({'tokens': [1, 2, 3]}).encode())
    monkeypatch.setattr('app.kepler_bridge.urllib.request.urlopen', open_request)
    assert preflight_context('http://kepler-engine:8080', 'Ola', 700) == (3, 4096)
    assert seen == ['http://kepler-engine:8080/props', 'http://kepler-engine:8080/tokenize']


def test_preflight_rejects_prompt_that_would_truncate(monkeypatch):
    from io import BytesIO
    def open_request(request, timeout):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith('/props'):
            return BytesIO(json.dumps({'default_generation_settings': {'n_ctx': 4096},
                                       'chat_template': '<|im_start|>user<|im_end|>'}).encode())
        return BytesIO(json.dumps({'tokens': list(range(3500))}).encode())
    monkeypatch.setattr('app.kepler_bridge.urllib.request.urlopen', open_request)
    with pytest.raises(ValueError, match='context exceeded'):
        preflight_context('http://kepler-engine:8080', 'long prompt', 700)
