from __future__ import annotations
import json
import logging
import os
import time
import threading
from pathlib import Path
from faster_whisper import WhisperModel
from .core import get_duration, propose_clips
from .timeline import build_timeline
from .director import direct_edit
from .edit_render import render_edited, read_assets
from .ranker import rerank_with_ollama
from .youtube import download_youtube, normalize_youtube_url
from .doctor import HEARTBEAT_KEY
from .store import INPUT
from .store import rconn, load, save, OUTPUT, JOBS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


def heartbeat_loop() -> None:
    """Keep a short-TTL heartbeat alive even while the model is generating."""
    while True:
        try:
            payload = {
                'at': time.time(),
                'ranker': os.getenv('CLIP_RANKER', 'heuristic').strip().lower(),
                'model': os.getenv('OLLAMA_MODEL', 'qwen2.5:3b'),
                'whisper_device': os.getenv('WHISPER_DEVICE', 'cpu'),
                'edit_director': os.getenv('EDIT_DIRECTOR', 'heuristic'),
                'render_engine': os.getenv('RENDER_ENGINE', 'remotion'),
            }
            rconn().setex(HEARTBEAT_KEY, 25, json.dumps(payload))
        except Exception as exc:
            log.warning('Heartbeat unavailable: %s', exc)
        time.sleep(5)


def record_ai_event(job: dict, event: str, details: dict) -> None:
    event_at = time.time()
    activity = job.setdefault('ai_activity', {})
    activity.update({'state': event, 'updated_at': event_at, **details})
    if event == 'analyzing':
        activity['started_at'] = event_at
        job['ranker_used'] = 'ollama_pending'
    elif event == 'completed':
        activity['elapsed_seconds'] = round(event_at - activity.get('started_at', event_at), 1)
        job['ranker_used'] = 'ollama'
    elif event == 'fallback':
        activity['elapsed_seconds'] = round(event_at - activity.get('started_at', event_at), 1)
        job['ranker_used'] = 'heuristic_fallback'
    save(job)
    log.info('AI job=%s event=%s details=%s', job['id'], event, details)


def process(jid: str) -> None:
    job = load(jid)
    if job["status"] != "QUEUED":
        return
    try:
        if job.get("source_type") == "youtube":
            if not job.get("platform_permission") or not job.get("license_note"):
                raise PermissionError("Autorização da plataforma e do titular precisam estar registradas")
            job["status"] = "DOWNLOADING"
            save(job)
            url = normalize_youtube_url(job["source_url"])
            source, metadata = download_youtube(url, INPUT / jid)
            job.update({"source": str(source), "youtube_metadata": metadata, "original_name": metadata["title"]})
            save(job)
        job["status"] = "TRANSCRIBING"
        save(job)
        source = Path(job["source"])
        if not source.exists():
            raise FileNotFoundError(source)
        duration = get_duration(source)
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        model_name = os.getenv("WHISPER_MODEL", "base")
        log.info("Transcribing %s using %s/%s/%s", jid, model_name, device, compute_type)
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        generator, info = model.transcribe(
            str(source), vad_filter=True, beam_size=int(os.getenv("WHISPER_BEAM_SIZE", "5")),
            word_timestamps=True, initial_prompt=os.getenv("WHISPER_INITIAL_PROMPT", "GTA VI, Rockstar Games, Vice City, Lucia, Jason, Leonida."),
        )
        segments = [{
            "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "text": w.word.strip()}
                      for w in (s.words or []) if w.start is not None and w.end is not None]
        } for s in generator]
        transcript_path = JOBS / f"{jid}.transcript.json"
        transcript_path.write_text(json.dumps({"language": info.language, "segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
        mode = os.getenv("CLIP_RANKER", "heuristic").strip().lower()
        if mode == "ollama":
            shortlist = propose_clips(segments, duration, count=16)
            record_ai_event(job, 'queued', {'total_candidates': min(len(shortlist), int(os.getenv('OLLAMA_SHORTLIST', '12')))})
            clips = rerank_with_ollama(shortlist, count=3, on_event=lambda event, details: record_ai_event(job, event, details))
            log.info("Ranker=ollama, shortlist=%s, clips=%s", len(shortlist), len(clips))
        else:
            job['ranker_used'] = 'heuristic'
            job['ai_activity'] = {'state': 'disabled', 'updated_at': time.time()}
            clips = propose_clips(segments, duration, count=3)
        if not clips:
            raise ValueError("No usable speech windows found; try a longer video with speech")
        job.update({"language": info.language, "duration": duration, "status": "RENDERING", "candidates": clips})
        save(job)
        folder = OUTPUT / jid
        folder.mkdir(parents=True, exist_ok=True)
        assets = read_assets()
        for i, clip in enumerate(clips):
            job["status"] = "DIRECTING"
            save(job)
            def on_director_event(event: str, details: dict):
                job["editing_activity"] = {"state": event, "updated_at": time.time(), **details}
                save(job)
                log.info("EDITOR job=%s clip=%s event=%s", jid, i+1, event)
            hints, director_used = direct_edit(clip, assets, on_event=on_director_event)
            timeline = build_timeline(clip, segments, edit=hints, assets=assets)
            video = folder / f"candidate_{i+1}.mp4"
            job["status"] = "RENDERING"
            save(job)
            renderer_used = render_edited(source, jid, i+1, clip, segments, timeline, assets, video)
            clip["file"] = str(video)
            clip["timeline_file"] = str(video.with_suffix(".timeline.json"))
            clip["director_used"] = director_used
            clip["renderer_used"] = renderer_used
            clip["word_count"] = len(timeline["layers"]["captions"])
            save(job)
        job["status"] = "NEEDS_REVIEW"
        save(job)
    except Exception as exc:
        log.exception("Failed job %s", jid)
        if job.get('ai_activity', {}).get('state') in ('queued', 'analyzing'):
            record_ai_event(job, 'failed', {'reason': str(exc)[:200]})
        job["status"] = "FAILED"
        job["error"] = str(exc)[:1500]
        save(job)


def main() -> None:
    threading.Thread(target=heartbeat_loop, daemon=True, name="worker-heartbeat").start()
    queue = rconn()
    log.info("Worker waiting on clips:queue")
    while True:
        try:
            item = queue.brpop("clips:queue", timeout=5)
            if item:
                process(item[1])
        except Exception:
            log.exception("worker loop error")
            time.sleep(3)

if __name__ == "__main__":
    main()
