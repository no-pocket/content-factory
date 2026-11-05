"""Reliable handoff for the single-worker Redis queue."""

PENDING = 'clips:queue'
PROCESSING = 'clips:processing'
TERMINAL = {'FAILED', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED'}


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
            job['status'] = 'QUEUED'
            job['error'] = None
            save_job(job)
            redis_client.lpush(PENDING, jid)
            recovered += 1
        redis_client.lrem(PROCESSING, 1, jid)
    return recovered
