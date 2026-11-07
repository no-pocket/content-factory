"""Checkpointed rendering for a single worker; retry never replaces siblings."""
from __future__ import annotations

import time
from pathlib import Path

from .director import direct_edit
from .edit_render import read_assets, render_edited
from .job_settings import normalize_job_settings
from .quality import inspect_candidate, normalize_qc
from .store import OUTPUT, save
from .service import invalidate_approvals
from .timeline import build_timeline, candidate_duration
from .artifacts import register_render, render_target

REVIEWABLE = {'VALID', 'WARNING'}


def render_candidates(job: dict, source: Path, segments: list, settings: dict,
                      audio_expected: bool, *, only: int | None = None) -> None:
    settings = normalize_job_settings(settings)
    limits = job['qc_settings'] = normalize_qc(job.get('qc_settings'))
    preview_size = (720, 1280) if settings['render_quality'] == 'high' else (540, 960)
    assets = read_assets()
    folder = OUTPUT / job['id']
    folder.mkdir(parents=True, exist_ok=True)
    for index, clip in enumerate(job['candidates']):
        if only is not None and index != only:
            continue
        target = Path(clip['file']) if clip.get('file') else folder / f'candidate_{index+1}.mp4'
        if clip.get('state') == 'RENDERING' and clip.get('attempt_history'):
            clip['attempt_history'][-1].update(state='FAILED', error='Worker interrupted', finished_at=time.time())
            clip['state'] = 'FAILED'
        # Recheck artifacts after interruptions; state alone does not prove integrity.
        if clip.get('state') in REVIEWABLE:
            current = inspect_candidate(target, candidate_duration(clip), audio_expected, limits, preview_size)
            if current['state'] in REVIEWABLE:
                clip['qc'] = current
                continue
            clip.update(state='FAILED', qc=current)
            invalidate_approvals(job, {index})
        while clip.get('attempts', 0) < limits['max_attempts']:
            render_revision = clip.get('render_revision', 0) + 1
            if job.get('editorial_protocol') == 2:
                target = render_target(job, index, render_revision)
                # Interrupted attempts may already have bytes; reserve a new directory.
                while target.parent.exists():
                    render_revision += 1
                    target = render_target(job, index, render_revision)
                target.parent.mkdir(parents=True, exist_ok=False)
                clip.update(file=str(target), timeline_file=str(target.with_suffix('.timeline.json')))
            clip['attempts'] = clip.get('attempts', 0) + 1
            attempt = {'number': clip['attempts'], 'started_at': time.time(), 'state': 'RENDERING'}
            clip.setdefault('attempt_history', []).append(attempt)
            clip['state'] = 'RENDERING'
            job['status'] = 'RENDERING'
            save(job)
            try:
                if 'timeline' not in clip:
                    job['status'] = 'DIRECTING'
                    save(job)
                    def event(name, details):
                        job['editing_activity'] = {'state': name, 'updated_at': time.time(), **details}
                        save(job)
                    hints, director_used = direct_edit(clip, assets, on_event=event,
                                                       mode=settings['director_mode'],
                                                       model=settings['llm_model'],
                                                       llm_backend=settings['llm_backend'])
                    clip['timeline'] = build_timeline(clip, segments, edit=hints, assets=assets)
                    clip['director_used'] = director_used
                    save(job)
                job['status'] = 'RENDERING'
                save(job)
                renderer = render_edited(source, job['id'], index + 1, clip, segments,
                                         clip['timeline'], assets, target, engine=settings['render_engine'], quality=settings['render_quality'])
                qc = inspect_candidate(target, candidate_duration(clip), audio_expected, limits, preview_size)
                clip.update(qc=qc, state=qc['state'], renderer_used=renderer,
                            file=str(target), timeline_file=str(target.with_suffix('.timeline.json')),
                            word_count=len(clip['timeline']['layers']['captions']))
                attempt.update(state=qc['state'], qc=qc)
            except Exception as exc:
                clip['state'] = 'FAILED'
                attempt.update(state='FAILED', error=str(exc)[:1500])
            attempt['finished_at'] = time.time()
            if job.get('editorial_protocol') == 2:
                register_render(job, index, revision=render_revision)
            save(job)
            # One attempt per dispatch. A human can retry this candidate within the saved limit.
            break
        if clip.get('state') == 'RENDERING':
            clip['state'] = 'FAILED'
            clip['attempt_history'][-1].update(state='FAILED', error='Interrupted attempt exhausted limit')
    states = [c.get('state') for c in job['candidates']]
    job['status'] = ('NEEDS_REVIEW' if all(s in REVIEWABLE for s in states) else
                     'PARTIAL_FAILED' if any(s in REVIEWABLE for s in states) else 'FAILED')
    job['error'] = None if job['status'] == 'NEEDS_REVIEW' else 'One or more candidates failed technical verification'
    job.pop('retry_candidate', None)
    if job.get('processing_runs') and job['processing_runs'][-1].get('state') == 'RUNNING':
        job['processing_runs'][-1].update(finished_at=time.time(), state='COMPLETED', timing_complete=True,
                                         seconds=round(time.time() - job['run_started_at'], 3))
    save(job)
