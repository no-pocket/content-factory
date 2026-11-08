from __future__ import annotations
import json
import os
import uuid
import time
import logging
from contextlib import contextmanager
from pathlib import Path
import redis
from .job_settings import normalize_job_settings
from .quality import normalize_qc

ROOT = Path(os.getenv("DATA_DIR", "data")).resolve()
JOBS = ROOT / "work"
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
for folder in (JOBS, INPUT, OUTPUT):
    folder.mkdir(parents=True, exist_ok=True)


def rconn():
    return redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def new_job(path: Path | None, filename: str, creator: str, license_note: str, *, source_url: str | None = None, platform_permission: bool = False, settings: dict | None = None) -> dict:
    jid = str(uuid.uuid4())
    record = {"schema_version": "1.0", "id": jid, "source": str(path) if path else None, "source_type": "youtube" if source_url else "upload",
              "source_url": source_url, "platform_permission": platform_permission, "original_name": filename,
              "creator": creator, "license_note": license_note, "status": "QUEUED", "candidates": [], "error": None,
              "approved": [], "created_at": time.time(), "settings_version": 1,
              "qc_settings": normalize_qc(), "decision_history": [],
              "settings": normalize_job_settings(settings), "model": os.getenv("WHISPER_MODEL", "base")}
    if record['settings']['outro_asset_id'] is not None:
        from .outro import snapshot_outro
        from .edit_render import read_assets
        record['outro_snapshot'] = snapshot_outro(record['settings']['outro_asset_id'], read_assets())
    record['editorial_protocol'] = record['settings']['editorial_protocol']
    from .editorial_policy import resolve_policy
    from .provenance import component_snapshot
    record['editorial_policy'] = resolve_policy(None)
    record['component_snapshot'] = component_snapshot(record['settings'])
    record['editorial_versions'] = {'brief_id': record['editorial_policy']['brief_id'],
                                    'brief_sha256': record['editorial_policy']['brief_sha256'],
                                    'component_snapshot_id': record['component_snapshot']['snapshot_id']}
    save(record)
    return record


def save(job: dict) -> None:
    """Atomic update: the dashboard never sees partially written job JSON."""
    for run in job.get('processing_runs', []):
        if run.get('state') == 'RUNNING':
            run['last_checkpoint_at'] = time.time()
    target = JOBS / (job["id"] + ".json")
    temp = JOBS / (job["id"] + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(7):
            try:
                os.replace(temp, target)
                break
            except PermissionError:
                # Windows readers on Docker bind mounts may briefly deny delete/rename.
                # Keep the old complete JSON until replacement succeeds; never truncate it.
                if attempt == 6:
                    raise
                logging.getLogger(__name__).warning('Job %s atomic replace temporarily blocked; retry=%s', job['id'], attempt + 1)
                time.sleep(.02 * 2 ** attempt)
    finally:
        temp.unlink(missing_ok=True)


def load(jid: str) -> dict:
    if not jid or not all(c.isalnum() or c == '-' for c in jid):
        raise ValueError("invalid id")
    return json.loads((JOBS / (jid + ".json")).read_text(encoding="utf-8"))


@contextmanager
def job_lock(jid: str):
    """Cross-process lock for idle-job mutations (HTTP and Streamlit)."""
    if not jid or not all(c.isalnum() or c == '-' for c in jid):
        raise ValueError('invalid id')
    with file_lock(JOBS / (jid + '.lock')):
        yield


@contextmanager
def file_lock(path: Path):
    """Lock a backend-owned local record across Streamlit/API processes."""
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            handle.write(b'0')
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def all_jobs() -> list[dict]:
    # Transcript sidecars share this directory but are not job records.
    records = []
    for path in JOBS.glob("*.json"):
        if path.name.endswith(".transcript.json"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and isinstance(record.get("id"), str) and record.get("id"):
            records.append(record)
    return sorted(records, key=lambda record: record["id"])
