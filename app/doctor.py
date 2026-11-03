"""Read-only checks and lightweight runtime telemetry for the private dashboard.

Worker heartbeat lives in Redis with an expiry. No model generation is triggered by
health checks, and failures are represented as offline/unknown rather than success.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

HEARTBEAT_KEY = 'clips:worker:heartbeat'


def _ollama_base() -> str:
    url = os.getenv('OLLAMA_URL', 'http://ollama:11434').rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('ollama', 'localhost', '127.0.0.1', 'host.docker.internal') or parsed.port not in (None, 11434):
        raise ValueError('OLLAMA_URL must point to an approved local Ollama host')
    return url


def _get_json(path: str) -> dict:
    request = urllib.request.Request(_ollama_base() + path, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=2.5) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError('Expected object response')
    return data


def worker_state(redis_client) -> dict:
    try:
        raw = redis_client.get(HEARTBEAT_KEY)
        data = json.loads(raw) if raw else None
        if not isinstance(data, dict):
            return {'online': False}
        age = max(0, time.time() - float(data.get('at', 0)))
        return {'online': age < 25, 'age_seconds': int(age), **data}
    except Exception as exc:
        return {'online': False, 'error': str(exc)[:180]}


def ollama_state(model: str) -> dict:
    result = {'reachable': False, 'installed': False, 'loaded': False, 'model': model}
    try:
        tags = _get_json('/api/tags')
        result['reachable'] = True
        names = [m.get('name', '') for m in tags.get('models', []) if isinstance(m, dict)]
        result['installed'] = model in names
        try:
            ps = _get_json('/api/ps')
            result['loaded'] = any(m.get('name') == model for m in ps.get('models', []) if isinstance(m, dict))
            result['running_models'] = [m.get('name') for m in ps.get('models', []) if isinstance(m, dict)]
        except (OSError, ValueError, urllib.error.URLError) as exc:
            result['ps_error'] = str(exc)[:180]
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result['error'] = str(exc)[:180]
    return result


def snapshot(redis_client) -> dict:
    worker = worker_state(redis_client)
    mode = worker.get('ranker', 'unknown') if worker.get('online') else 'unknown'
    model = worker.get('model', os.getenv('OLLAMA_MODEL', 'qwen2.5:3b'))
    return {'worker': worker, 'ranker': mode, 'ollama': ollama_state(model)}
