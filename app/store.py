from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
import redis
from .job_settings import normalize_job_settings

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
              "approved": [], "settings": normalize_job_settings(settings), "model": os.getenv("WHISPER_MODEL", "base")}
    save(record)
    return record


def save(job: dict) -> None:
    """Atomic update: the dashboard never sees partially written job JSON."""
    target = JOBS / (job["id"] + ".json")
    temp = JOBS / (job["id"] + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def load(jid: str) -> dict:
    if not jid or not all(c.isalnum() or c == '-' for c in jid):
        raise ValueError("invalid id")
    return json.loads((JOBS / (jid + ".json")).read_text(encoding="utf-8"))


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
