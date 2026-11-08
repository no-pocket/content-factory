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
from .telemetry import measure_stage, job_metric_context

REVIEWABLE = {'VALID', 'WARNING'}


def _validate_duration(clip: dict, settings: dict) -> None:
    """A cached timeline cannot elevate the saved duration opt-in or window."""
    import math
    mode = settings.get('duration_mode', 'classic')
    timeline = clip.get('timeline') or {}
    if mode == 'classic':
        if clip.get('duration_mode', 'classic') != 'classic' or timeline.get('duration_mode', 'classic') != 'classic':
            raise ValueError('Flexible duration requires saved opt-in')
        return
    duration = clip.get('assembly', {}).get('duration', clip['end'] - clip['start'])
    if not math.isfinite(duration) or not settings['min_seconds'] <= duration <= settings['max_seconds']:
        raise ValueError('Candidate duration outside saved flexible bounds')
    if 'duration' in timeline and (not math.isfinite(timeline['duration'])
            or abs(timeline['duration'] - duration) > .002
            or not settings['min_seconds'] <= timeline['duration'] <= settings['max_seconds']):
        raise ValueError('Cached timeline duration differs from saved source window')


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
            with measure_stage(clip.setdefault('stage_metrics',[]),'QC',job_metric_context(job,index,clip.get('render_revision')),
                               requested='resume_full_decode',resolved='ffmpeg_ffprobe') as metric:
                try:
                    _validate_duration(clip, settings)
                    current = inspect_candidate(target, candidate_duration(clip), audio_expected, limits, preview_size)
                except ValueError as exc:
                    current = {'state':'FAILED', 'errors':[str(exc)]}
                metric['qc_state']=current['state']
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
            metric_start=len(clip.setdefault('stage_metrics',[]))
            metric_context=job_metric_context(job,index,render_revision)
            clip['editorial_versions']={**job.get('editorial_versions',{'brief_id':'UNKNOWN','brief_sha256':'UNKNOWN'}),
                                       'component_snapshot_id':metric_context['component_snapshot_id']}
            job['status'] = 'RENDERING'
            save(job)
            try:
                _validate_duration(clip, settings)
                if settings.get('duration_mode') == 'flexible' and 'timeline' not in clip:
                    clip['duration_mode'] = 'flexible'
                from .outro import validate_job_outro
                outro_snapshot = validate_job_outro({**job, 'settings':settings}, assets)
                if settings['director_mode'] == 'external' and 'timeline' not in clip:
                    raise ValueError('External model timeline missing; heuristic direction is forbidden')
                if clip.get('editorial_context'):
                    from .editorial_story import assess_story, validate_story_boundary
                    story = assess_story(clip['editorial_context'], {}, clip.get('model_story'))
                    clip['story_assessment'] = story
                    # Historical v2 windows were rounded to centiseconds. Keep their
                    # saved bytes/timing; this allowance never applies to new/v3 plans.
                    tolerance = .005001 if clip.get('timeline',{}).get('schema_version') == '2.0' else 1e-6
                    validate_story_boundary({'source_start': clip['start'], 'source_end': clip['end']}, clip['editorial_context'], tolerance=tolerance)
                    if tolerance > 1e-6:
                        clip['boundary_compatibility'] = {'centisecond_rounding_tolerance_seconds':tolerance}
                    if story['closure'] == 'INCOMPLETE':
                        raise ValueError('Editorial story incomplete: no validated payoff within selected duration; choose another interval')
                if 'timeline' not in clip:
                    job['status'] = 'DIRECTING'
                    save(job)
                    def event(name, details):
                        job['editing_activity'] = {'state': name, 'updated_at': time.time(), **details}
                        save(job)
                    with measure_stage(clip['stage_metrics'],'DIRECTOR',metric_context,
                                       requested={'mode':settings['director_mode'],'model':settings['llm_model'],'backend':settings['llm_backend']}) as metric:
                        hints, director_used = direct_edit(clip, assets, on_event=event,
                                                           mode=settings['director_mode'],
                                                           model=settings['llm_model'],
                                                           llm_backend=settings['llm_backend'])
                        metric['resolved']=director_used
                        if 'fallback' in director_used:
                            metric['fallback_reason']=job.get('editing_activity',{}).get('reason','UNKNOWN')
                    if clip.get('editorial_context'):
                        clip['story_assessment'] = assess_story(clip['editorial_context'], {}, hints.get('story'))
                        if clip['story_assessment']['closure'] == 'INCOMPLETE':
                            raise ValueError('Editorial model found incomplete closure; a new validated boundary is required')
                    clip['timeline'] = build_timeline(clip, segments, edit=hints, assets=assets)
                    clip['director_used'] = director_used
                    save(job)
                else:
                    with measure_stage(clip['stage_metrics'],'DIRECTOR',metric_context,requested=settings['director_mode'],
                                       resolved=clip.get('director_used','UNKNOWN')) as metric:
                        metric['state']='CACHED'
                job['status'] = 'RENDERING'
                save(job)
                renderer = render_edited(source, job['id'], index + 1, clip, segments,
                                         clip['timeline'], assets, target, engine=settings['render_engine'], quality=settings['render_quality'],
                                         metrics=clip['stage_metrics'],metric_context=metric_context,
                                         outro_asset_id=settings['outro_asset_id'], outro_snapshot=outro_snapshot)
                with measure_stage(clip['stage_metrics'],'QC',metric_context,requested='mp4_webm_full_decode',resolved='ffmpeg_ffprobe') as metric:
                    qc = inspect_candidate(target, candidate_duration(clip), audio_expected, limits, preview_size)
                    metric['qc_state']=qc['state']
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
                for metric in clip['stage_metrics'][metric_start:]:
                    metric.update(candidate_version=clip['candidate_version'],render_revision=clip['render_revision'])
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
