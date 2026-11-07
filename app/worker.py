from __future__ import annotations
import json
import logging
import os
import time
import threading
from pathlib import Path
from faster_whisper import WhisperModel
from .core import get_duration, propose_clips
from .errors import describe_failure
from .candidates import render_candidates
from .quality import expects_audio, normalize_qc
from .ranker import select_highlights
from .youtube import download_youtube, normalize_youtube_url
from .doctor import HEARTBEAT_KEY
from .store import INPUT
from .store import rconn, load, save, all_jobs, JOBS
from .queueing import PENDING, PROCESSING, TERMINAL, recover_inflight, reconcile_pending, close_interrupted_run
from .job_settings import normalize_job_settings

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
    job.setdefault('ai_events', []).append({'at': event_at, 'event': event, 'details': dict(details)})
    activity = job.setdefault('ai_activity', {})
    activity.update({'state': event, 'updated_at': event_at, **details})
    backend = job.get('settings', {}).get('llm_backend', 'ollama')
    if event == 'analyzing':
        activity['started_at'] = event_at
        job['ranker_used'] = backend + '_pending'
    elif event == 'completed':
        activity['elapsed_seconds'] = round(event_at - activity.get('started_at', event_at), 1)
        job['ranker_used'] = backend
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
        raw_settings = dict(job.get('settings') or {})
        raw_settings.setdefault('render_quality', 'standard')  # preserve pre-profile job intent
        settings = job['settings'] = normalize_job_settings(raw_settings)
        job['qc_settings'] = normalize_qc(job.get('qc_settings'))
        job['run_started_at'] = time.time()
        close_interrupted_run(job)
        job.setdefault('processing_runs', []).append({'started_at': job['run_started_at'], 'state': 'RUNNING'})
        save(job)
        if job.get("source_type") == "youtube" and not job.get("source"):
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
        transcript_path = JOBS / f"{jid}.transcript.json"
        if transcript_path.is_file():
            transcript = json.loads(transcript_path.read_text(encoding='utf-8'))
            segments = transcript['segments']
        else:
            device = os.getenv("WHISPER_DEVICE", "cpu")
            compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
            model_name = settings['whisper_model']
            job['model'] = model_name
            log.info("Transcribing %s using %s/%s/%s", jid, model_name, device, compute_type)
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            generator, info = model.transcribe(
                str(source), vad_filter=True, beam_size=settings['whisper_beam_size'],
                word_timestamps=True, initial_prompt=os.getenv("WHISPER_INITIAL_PROMPT", "GTA VI, Rockstar Games, Vice City, Lucia, Jason, Leonida."),
            )
            segments = [{
                "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
                "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "text": w.word.strip()}
                          for w in (s.words or []) if w.start is not None and w.end is not None]
            } for s in generator]
            transcript = {"language": info.language, "segments": segments}
            pending = transcript_path.with_suffix(".tmp")
            pending.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(pending, transcript_path)
        if job.get('candidates'):
            clips = job['candidates']
        else:
            mode = settings['ranker_mode']
            if mode == "ollama":
                record_ai_event(job, 'queued', {'transcript_segments': len(segments)})
                clips = select_highlights(segments, duration, count=settings['clip_count'], settings=settings,
                                          on_event=lambda event, details: record_ai_event(job, event, details))
                log.info("Ranker=ollama transcript discovery, clips=%s", len(clips))
            else:
                job['ranker_used'] = 'heuristic'
                job['ai_activity'] = {'state': 'disabled', 'updated_at': time.time()}
                clips = propose_clips(segments, duration, count=settings['clip_count'],
                                      target=settings['target_seconds'], min_seconds=settings['min_seconds'],
                                      max_seconds=settings['max_seconds'])
        if not clips:
            raise ValueError("No usable speech windows found; try a longer video with speech")
        job.update({"language": transcript['language'], "duration": duration, "status": "RENDERING", "candidates": clips})
        if 'audio_expected' not in job:
            job['audio_expected'] = expects_audio(source)
        save(job)
        render_candidates(job, source, segments, settings, job['audio_expected'], only=job.get('retry_candidate'))
    except Exception as exc:
        log.exception("Failed job %s", jid)
        if job.get('ai_activity', {}).get('state') in ('queued', 'analyzing'):
            record_ai_event(job, 'failed', {'reason': str(exc)[:200]})
        job["status"] = "FAILED"
        job["error"] = describe_failure(exc)
        if job.get('processing_runs') and job['processing_runs'][-1].get('state') == 'RUNNING':
            job['processing_runs'][-1].update(state='FAILED', finished_at=time.time(), timing_complete=True,
                                              seconds=time.time() - job['run_started_at'])
        save(job)


def main() -> None:
    threading.Thread(target=heartbeat_loop, daemon=True, name="worker-heartbeat").start()
    queue = rconn()
    recovered = recover_inflight(queue, load, save)
    recovered += reconcile_pending(queue, all_jobs())
    log.info("Worker waiting on %s; recovered=%s", PENDING, recovered)
    while True:
        try:
            jid = queue.brpoplpush(PENDING, PROCESSING, timeout=5)
            if jid:
                process(jid)
                if load(jid).get('status') in TERMINAL:
                    queue.lrem(PROCESSING, 1, jid)
        except Exception:
            log.exception("worker loop error")
            time.sleep(3)

if __name__ == "__main__":
    main()
