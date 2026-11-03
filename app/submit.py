"""Queue a licensed single-video YouTube URL for future Hermes agent integration.

Usage: python -m app.submit --file /path/to/agent-request.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.store import new_job, rconn
from app.youtube import normalize_youtube_url


def submit(payload: dict) -> dict:
    required = ("source_url", "creator", "license_note")
    if any(not isinstance(payload.get(k), str) or not payload[k].strip() for k in required):
        raise ValueError("source_url, creator e license_note são obrigatórios")
    if payload.get("rights_confirmed") is not True or payload.get("platform_permission") is not True:
        raise PermissionError("A autorização do titular e da plataforma deve ser confirmada")
    url = normalize_youtube_url(payload["source_url"])
    job = new_job(None, url, payload["creator"].strip(), payload["license_note"].strip(), source_url=url, platform_permission=True)
    rconn().lpush("clips:queue", job["id"])
    return {"job_id": job["id"], "status": job["status"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(submit(json.loads(args.file.read_text(encoding="utf-8"))), ensure_ascii=False))

if __name__ == "__main__":
    main()
