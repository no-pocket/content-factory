"""Synthetic corpus files; never creates real jobs or editorial decisions."""
import io

import pytest

from research import batch_editorial as batch


def test_batch_is_idempotent_by_content_and_requires_authorization(monkeypatch, tmp_path):
    videos = tmp_path / 'videos'
    videos.mkdir()
    (videos / 'português.mp4').write_bytes(b'synthetic pt')
    (videos / 'english.mp4').write_bytes(b'synthetic en')
    records = []
    monkeypatch.setattr(batch, 'all_jobs', lambda: records[:])
    def create(payload, *, upload, filename):
        import hashlib
        job = {'id': str(len(records)), 'status': 'QUEUED', 'source_fingerprint': hashlib.sha256(upload.read()).hexdigest(),
               'settings': payload['settings'], 'evaluation': payload['evaluation']}
        records.append(job)
        return job
    monkeypatch.setattr(batch, 'create_job', create)
    with pytest.raises(PermissionError):
        batch.prepare(videos, 'synthetic', '', tmp_path / 'manifest.json')
    first = batch.prepare(videos, 'synthetic', 'synthetic grant', tmp_path / 'manifest.json')
    (videos / 'added-after-corpus-freeze.mp4').write_bytes(b'new video outside this round')
    second = batch.prepare(videos, 'synthetic', 'synthetic grant', tmp_path / 'manifest.json')
    assert first == second
    assert len(records) == 2
    assert batch.BASELINE['whisper_model'] == 'base'


def test_human_review_does_not_skip_signal_analysis(monkeypatch, tmp_path):
    monkeypatch.setattr(batch, 'load', lambda jid: {'id': jid, 'status': 'APPROVED',
                                                   'original_name': 'english.mp4', 'language': 'en',
                                                   'candidates': []})
    calls = []
    def signals(job):
        calls.append(job['id'])
        return {'synthetic': True}
    monkeypatch.setattr(batch, 'signals', signals)
    batch.observe([{'job_id': 'reviewed'}], tmp_path / 'manifest.json', analyze=True)
    assert calls == ['reviewed']
    assert (tmp_path / 'signals-reviewed.json').is_file()
