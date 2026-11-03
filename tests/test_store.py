import json
from app import store


def test_all_jobs_skips_transcript_and_invalid_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "JOBS", tmp_path)
    (tmp_path / "a.json").write_text(json.dumps({"id": "a", "status": "QUEUED"}))
    (tmp_path / "a.transcript.json").write_text(json.dumps({"language": "pt", "segments": []}))
    (tmp_path / "bad.json").write_text("{incomplete")
    (tmp_path / "unrelated.json").write_text(json.dumps({"value": 123}))
    assert [job["id"] for job in store.all_jobs()] == ["a"]
