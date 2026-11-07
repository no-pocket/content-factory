"""Reliable handoff for the single-worker Redis queue."""

PENDING = 'clips:queue'
PROCESSING = 'clips:processing'
TERMINAL = {'FAILED', 'QUEUE_FAILED', 'PARTIAL_FAILED', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED'}


def close_interrupted_run(job: dict) -> None:
    for run in job.get('processing_runs', []):
        if run.get('state') == 'RUNNING':
            run.update(state='INTERRUPTED', timing_complete=False,
                       seconds=max(0, run.get('last_checkpoint_at', run['started_at']) - run['started_at']))


def reconcile_pending(redis_client, jobs: list[dict]) -> int:
    """Single-worker startup repairs crash between saving a record and enqueueing it."""
    present = set(redis_client.lrange(PENDING, 0, -1)) | set(redis_client.lrange(PROCESSING, 0, -1))
    count = 0
    for job in jobs:
        if job.get('status') == 'QUEUED' and job['id'] not in present:
            redis_client.lpush(PENDING, job['id'])
            present.add(job['id'])
            count += 1
    return count


def recover_inflight(redis_client, load_job, save_job) -> int:
    """Replay jobs left in the processing list by an interrupted worker."""
    recovered = 0
    for jid in redis_client.lrange(PROCESSING, 0, -1):
        try:
            job = load_job(jid)
        except (OSError, ValueError, KeyError):
            redis_client.lrem(PROCESSING, 1, jid)
            continue
        if job.get('status') not in TERMINAL:
            close_interrupted_run(job)
            job['status'] = 'QUEUED'
            job['error'] = None
            save_job(job)
            redis_client.lpush(PENDING, jid)
            recovered += 1
        redis_client.lrem(PROCESSING, 1, jid)
    return recovered
