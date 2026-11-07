import json
from pathlib import Path

import pytest

from app import worker, store, service
from app.queueing import reconcile_pending


def test_recovery_reuses_transcript_selection_and_settings(monkeypatch, tmp_path):
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'fixture')
    job = {'id': 'checkpoint', 'status': 'QUEUED', 'source': str(source), 'audio_expected': True,
           'candidates': [{'start': 1, 'end': 20, 'state': 'VALID', 'file': 'keep'}],
           'settings': {'ranker_mode': 'heuristic'}}
    job['retry_candidate'] = 0
    (tmp_path / 'checkpoint.transcript.json').write_text(json.dumps({'language': 'pt', 'segments': []}))
    monkeypatch.setattr(worker, 'JOBS', tmp_path)
    monkeypatch.setattr(worker, 'load', lambda jid: job)
    monkeypatch.setattr(worker, 'save', lambda job: None)
    monkeypatch.setattr(worker, 'get_duration', lambda p: 100)
    def forbidden(*a, **k):
        pytest.fail('Completed stage was repeated')
    monkeypatch.setattr(worker, 'WhisperModel', forbidden)
    monkeypatch.setattr(worker, 'propose_clips', forbidden)
    def render(record, *args, **kwargs):
        assert record['candidates'][0]['file'] == 'keep'
        assert record.get('retry_candidate') == 0
        assert kwargs['only'] == 0
        record['status'] = 'NEEDS_REVIEW'
    monkeypatch.setattr(worker, 'render_candidates', render)
    worker.process('checkpoint')
    assert job['status'] == 'NEEDS_REVIEW'


def test_queue_failure_persists_and_explicit_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    job = store.new_job(None, 'video', 'creator', 'grant')
    class Queue:
        def lpush(self, *a):
            raise ConnectionError('offline')
    with pytest.raises(RuntimeError, match=job['id']):
        service.enqueue(job, Queue())
    assert store.load(job['id'])['status'] == 'QUEUE_FAILED'
    queued = []
    queue = type('Queue', (), {'lpush': lambda self, key, jid: queued.append(jid)})()
    service.retry_enqueue(job['id'], queue=queue)
    assert queued == [job['id']]


def test_orphan_queued_record_reconciles_once():
    class Queue:
        pending = ['already']
        def lrange(self, key, *a):
            return self.pending[:] if key == 'clips:queue' else []
        def lpush(self, key, jid):
            self.pending.append(jid)
    queue = Queue()
    jobs = [{'id': 'orphan', 'status': 'QUEUED'}, {'id': 'already', 'status': 'QUEUED'},
            {'id': 'review', 'status': 'NEEDS_REVIEW'}]
    assert reconcile_pending(queue, jobs) == 1
    assert reconcile_pending(queue, jobs) == 0


def test_interrupted_time_preserved_as_lower_bound():
    from app.queueing import close_interrupted_run
    job = {'processing_runs': [{'started_at': 10, 'last_checkpoint_at': 50, 'state': 'RUNNING'}]}
    close_interrupted_run(job)
    run = job['processing_runs'][0]
    assert run['seconds'] == 40
    assert run['state'] == 'INTERRUPTED'
    assert run['timing_complete'] is False
