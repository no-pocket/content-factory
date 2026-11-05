import json
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
