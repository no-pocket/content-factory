import copy
import uuid
import pytest
from app import store, service
from test_source_ingestion import Queue as IngestionQueue, setup
from test_hermes_api import hermes_server


class Queue(IngestionQueue):
    def lpos(self, key, value):
        return 0 if value in getattr(self, 'processing', []) else None


def failed_job():
    job = store.new_job(None, 'Synthetic video', 'Owner', 'Test grant',
                        settings={'editorial_protocol': 2, 'duration_mode': 'flexible'})
    job.update(status='FAILED', error='No usable speech windows found; try a longer video with speech',
               processing_runs=[{'run_id': str(uuid.uuid4()), 'state': 'FAILED'}])
    store.save(job)
    return job


def request(job):
    return {'request_id': str(uuid.uuid4()), 'expected_run_id': job['processing_runs'][-1]['run_id']}


def test_reprocess_is_idempotent_preserves_snapshot_and_records_failure(setup):
    job = failed_job(); settings = copy.deepcopy(job['settings']); q = Queue(); action = request(job)
    service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse este job.', actor_id='telegram:123', queue=q)
    service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse este job.', actor_id='telegram:123', queue=q)
    saved = store.load(job['id'])
    assert saved['status'] == 'QUEUED' and saved['settings'] == settings
    assert saved['processing_runs'] == job['processing_runs']
    assert len(q.ids) == 1
    assert saved['reprocess_requests'][action['request_id']]['previous_error'] == job['error']
    with pytest.raises(service.Conflict):
        service.reprocess_failed_job(job['id'], action, owner_message='Outra instrução.', actor_id='telegram:123', queue=q)


def test_reprocess_lost_queue_reply_recovers_and_never_retries_twice(setup):
    class LostReply(Queue):
        def eval(self, *args):
            super().eval(*args)
            raise OSError('reply lost')
    job = failed_job(); action = request(job); q = LostReply()
    with pytest.raises(RuntimeError):
        service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse.', actor_id='telegram:123', queue=q)
    q.eval = Queue.eval.__get__(q)
    service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse.', actor_id='telegram:123', queue=q)
    assert len(q.ids) == 1
    saved = store.load(job['id']); saved['status'] = 'FAILED'; store.save(saved)
    service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse.', actor_id='telegram:123', queue=q)
    assert store.load(job['id'])['status'] == 'FAILED' and len(q.ids) == 1


@pytest.mark.parametrize('change', [{'status':'RENDERING'}, {'candidates':[{'state':'FAILED'}]}])
def test_reprocess_refuses_active_jobs_and_existing_candidates(setup, change):
    job = failed_job(); job.update(change); store.save(job); q = Queue()
    with pytest.raises(service.Conflict):
        service.reprocess_failed_job(job['id'], request(job), owner_message='Reprocesse.', actor_id='telegram:123', queue=q)
    assert not q.ids


def test_hermes_reprocess_requires_explicit_current_intent_and_returns_diagnostics(setup, hermes_server, monkeypatch):
    job = failed_job(); q = Queue(); monkeypatch.setattr(store, 'rconn', lambda:q)
    status, result = hermes_server('/v2/hermes/jobs/'+job['id'])
    assert result['failure']['code'] == 'NO_USABLE_CANDIDATES'
    path = '/v2/hermes/jobs/'+job['id']+'/reprocess'; action = request(job)
    assert hermes_server(path, {'reprocess':action})[0] == 422
    body = {'owner_message':'Reprocesse este job.', 'reprocess':action}
    stale = {**action, 'expected_run_id':str(uuid.uuid4())}
    assert hermes_server(path, {**body, 'reprocess':stale})[0] == 409
    assert hermes_server(path, body)[0] == 200
    assert hermes_server(path, body)[0] == 200
    assert q.ids == [job['id']]


def test_reprocess_concurrent_same_request_enqueues_once(setup):
    from concurrent.futures import ThreadPoolExecutor
    job = failed_job(); action = request(job); q = Queue()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: service.reprocess_failed_job(job['id'], action,
            owner_message='Reprocesse.', actor_id='telegram:123', queue=q), range(4)))
    assert q.ids == [job['id']]


def test_reprocess_waits_for_worker_terminal_acknowledgment(setup):
    job = failed_job(); action = request(job); q = Queue(); q.processing = [job['id']]
    with pytest.raises(service.Conflict, match='acknowledg'):
        service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse.', actor_id='telegram:123', queue=q)
    assert store.load(job['id'])['status'] == 'FAILED' and not q.ids
    q.processing.clear()
    service.reprocess_failed_job(job['id'], action, owner_message='Reprocesse.', actor_id='telegram:123', queue=q)
    assert q.ids == [job['id']]


def test_hermes_reprocess_cannot_bypass_local_scope(setup, hermes_server, monkeypatch):
    job = failed_job(); job['source_snapshot'] = {'allowed_model_scopes':['local']}; store.save(job)
    q = Queue(); monkeypatch.setattr(store, 'rconn', lambda:q)
    body = {'owner_message':'Reprocesse.', 'reprocess':request(job)}
    assert hermes_server('/v2/hermes/jobs/'+job['id']+'/reprocess', body)[0] == 403
    assert not q.ids and store.load(job['id'])['status'] == 'FAILED'
