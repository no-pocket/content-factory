"""Queue a licensed single-video YouTube URL for future Hermes agent integration.

Usage: python -m app.submit --file /path/to/agent-request.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.store import new_job, rconn
from app.youtube import normalize_youtube_url
from app.service import create_job


def submit(payload: dict) -> dict:
    if not payload.get('source_url'):
        raise ValueError('source_url required')
    job = create_job(payload, queue=rconn())
    return {"job_id": job["id"], "status": job["status"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(submit(json.loads(args.file.read_text(encoding="utf-8"))), ensure_ascii=False))

if __name__ == "__main__":
    main()
