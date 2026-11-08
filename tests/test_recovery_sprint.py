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


def test_fresh_numpy_asr_matches_cached_context(monkeypatch, tmp_path):
    import numpy as np
    from types import SimpleNamespace
    from app.editorial_context import build_candidate_context
    source=tmp_path/'speech.mp4'; source.write_bytes(b'synthetic')
    job={'id':'numpy-asr','status':'QUEUED','source':str(source),'audio_expected':True,
         'settings':{'duration_mode':'flexible'},'candidates':[]}
    word=SimpleNamespace(start=np.float64(.68),end=np.float64(1.12),word=' Fala')
    segment=SimpleNamespace(start=np.float64(.68),end=np.float64(8.32),text=' Fala completa.',words=[word])
    class Model:
        def transcribe(self,*a,**k): return iter([segment]),SimpleNamespace(language='pt')
    monkeypatch.setattr(worker,'WhisperModel',lambda *a,**k: Model())
    monkeypatch.setattr(worker,'JOBS',tmp_path)
    monkeypatch.setattr(worker,'load',lambda jid:job)
    monkeypatch.setattr(worker,'save',lambda record:None)
    monkeypatch.setattr(worker,'get_duration',lambda path:10)
    def select(segments,*a,**k):
        context_job={'candidates':[{'start':0,'end':9}]}
        fresh={'language':'pt','segments':segments}
        cached=json.loads((tmp_path/'numpy-asr.transcript.json').read_text())
        assert type(segments[0]['start']) is float
        assert type(segments[0]['words'][0]['end']) is float
        assert build_candidate_context(context_job,0,fresh) == build_candidate_context(context_job,0,cached)
        return [{'start':0,'end':9}]
    monkeypatch.setattr(worker,'select_highlights',select)
    monkeypatch.setattr(worker,'render_candidates',lambda record,*a,**k:record.update(status='NEEDS_REVIEW'))
    worker.process(job['id'])
    assert job['status'] == 'NEEDS_REVIEW'


@pytest.mark.parametrize('start,end',[(float('nan'),2),(0,float('inf')),(-1,2),(2,1),(True,2)])
def test_asr_boundary_rejects_invalid_segment_timing(start,end):
    from types import SimpleNamespace
    segment=SimpleNamespace(start=start,end=end,text='Invalid',words=[])
    with pytest.raises(ValueError,match='ASR'):
        worker.serialize_asr_segments([segment])
