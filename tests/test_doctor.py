import json
import time
from app import doctor

class FakeRedis:
    def __init__(self, data=None):
        self.data = data
    def get(self, _):
        return self.data


def test_heartbeat_live_and_stale():
    live = doctor.worker_state(FakeRedis(json.dumps({'at': time.time(), 'ranker': 'ollama', 'model': 'qwen2.5:3b'})))
    assert live['online'] and live['ranker'] == 'ollama'
    stale = doctor.worker_state(FakeRedis(json.dumps({'at': time.time() - 50, 'ranker': 'ollama'})))
    assert not stale['online']
    assert not doctor.worker_state(FakeRedis())['online']


def test_doctor_online_installed_loaded(monkeypatch):
    monkeypatch.setattr(doctor, '_get_json', lambda path: {'models': [{'name': 'qwen2.5:3b'}]})
    result = doctor.ollama_state('qwen2.5:3b')
    assert result['reachable'] and result['installed'] and result['loaded']


def test_doctor_missing_model(monkeypatch):
    monkeypatch.setattr(doctor, '_get_json', lambda path: {'models': []})
    result = doctor.ollama_state('qwen2.5:3b')
    assert result['reachable'] and not result['installed'] and not result['loaded']


def test_doctor_offline(monkeypatch):
    def fail(_):
        raise ConnectionError('offline')
    monkeypatch.setattr(doctor, '_get_json', fail)
    result = doctor.ollama_state('qwen2.5:3b')
    assert not result['reachable']


def test_restricted_ollama_url(monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://example.org:11434')
    import pytest
    with pytest.raises(ValueError):
        doctor._ollama_base()
