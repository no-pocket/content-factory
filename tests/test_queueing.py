from app.queueing import recover_inflight


class FakeRedis:
    def __init__(self, processing):
        self.processing = list(processing)
        self.pending = []

    def lrange(self, key, start, stop):
        return list(self.processing)

    def lrem(self, key, count, value):
        self.processing.remove(value)

    def lpush(self, key, value):
        self.pending.insert(0, value)


def test_recovery_requeues_interrupted_job_and_skips_completed_one():
    redis = FakeRedis(['running', 'done'])
    jobs = {'running': {'id': 'running', 'status': 'TRANSCRIBING'},
            'done': {'id': 'done', 'status': 'NEEDS_REVIEW'}}
    saved = []
    recover_inflight(redis, jobs.__getitem__, lambda job: saved.append(dict(job)))
    assert redis.processing == []
    assert redis.pending == ['running']
    assert jobs['running']['status'] == 'QUEUED'
    assert saved[0]['status'] == 'QUEUED'


def test_recovery_discards_missing_record_without_stopping_other_jobs():
    redis = FakeRedis(['missing', 'valid'])
    jobs = {'valid': {'id': 'valid', 'status': 'RENDERING'}}
    recover_inflight(redis, jobs.__getitem__, lambda job: None)
    assert redis.pending == ['valid']
    assert redis.processing == []

def test_recovery_preserves_job_waiting_for_external_editorial_plan():
    redis = FakeRedis(['waiting'])
    jobs = {'waiting': {'id':'waiting', 'status':'WAITING_EDITORIAL_PLAN'}}
    saved = []
    assert recover_inflight(redis, jobs.__getitem__, lambda job: saved.append(dict(job))) == 0
    assert jobs['waiting']['status'] == 'WAITING_EDITORIAL_PLAN'
    assert redis.pending == []
    assert redis.processing == []

def test_recovery_does_not_requeue_editorial_no_candidates():
    redis=FakeRedis(['empty'])
    jobs={'empty':{'id':'empty','status':'EDITORIAL_NO_CANDIDATES'}}
    assert recover_inflight(redis,jobs.__getitem__,lambda _:None)==0
    assert redis.pending==[] and jobs['empty']['status']=='EDITORIAL_NO_CANDIDATES'
