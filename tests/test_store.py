import json
import pytest
from app import store


def test_all_jobs_skips_transcript_and_invalid_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "JOBS", tmp_path)
    (tmp_path / "a.json").write_text(json.dumps({"id": "a", "status": "QUEUED"}))
    (tmp_path / "a.transcript.json").write_text(json.dumps({"language": "pt", "segments": []}))
    (tmp_path / "bad.json").write_text("{incomplete")
    (tmp_path / "unrelated.json").write_text(json.dumps({"value": 123}))
    assert [job["id"] for job in store.all_jobs()] == ["a"]


def test_new_job_persists_processing_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    job = store.new_job(tmp_path / 'video.mp4', 'video.mp4', 'creator', 'grant',
                        settings={'clip_count': 5, 'target_seconds': 30})
    loaded = store.load(job['id'])
    assert loaded['settings']['clip_count'] == 5
    assert loaded['settings']['target_seconds'] == 30
    assert loaded['settings']['proposal_max_chunks'] == 12


def test_atomic_save_retries_transient_windows_reader_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    replace = store.os.replace
    calls = []
    def blocked(source, target):
        calls.append(1)
        if len(calls) <= 2:
            raise PermissionError('Windows reader sharing violation')
        replace(source, target)
    monkeypatch.setattr(store.os, 'replace', blocked)
    monkeypatch.setattr(store.time, 'sleep', lambda seconds: None)
    store.save({'id': 'transient', 'status': 'RENDERING'})
    assert store.load('transient')['status'] == 'RENDERING'
    assert len(calls) == 3


def test_persistent_atomic_save_failure_keeps_previous_record(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    store.save({'id': 'blocked', 'status': 'NEEDS_REVIEW'})
    def blocked(*args):
        raise PermissionError('Permanent write denial')
    monkeypatch.setattr(store.os, 'replace', blocked)
    monkeypatch.setattr(store.time, 'sleep', lambda seconds: None)
    with pytest.raises(PermissionError):
        store.save({'id': 'blocked', 'status': 'RENDERING'})
    assert store.load('blocked')['status'] == 'NEEDS_REVIEW'
    assert list(tmp_path.glob('*.tmp')) == []
