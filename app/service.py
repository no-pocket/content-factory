"""Application boundary shared by Streamlit, CLI and HTTP v1."""
from __future__ import annotations

import hashlib
import os
import shutil
import time
import uuid
from pathlib import Path

from . import store
from .editorial import config_id, validate_decision, current_decisions
from .job_settings import normalize_job_settings
from .quality import normalize_qc, inspect_candidate
from .youtube import normalize_youtube_url
from .timeline import candidate_duration


class Conflict(ValueError):
    pass


def enqueue(job: dict, queue=None) -> dict:
    try:
        (queue or store.rconn()).lpush('clips:queue', job['id'])
    except Exception as exc:
        job.update(status='QUEUE_FAILED', error='Queue unavailable; retry enqueue through backend')
        store.save(job)
        raise RuntimeError('Queue unavailable; job_id=' + job['id']) from exc
    return job


def create_job(payload: dict, *, upload=None, filename: str | None = None, queue=None) -> dict:
    for key in ('creator', 'license_note'):
        if not isinstance(payload.get(key), str) or not payload[key].strip() or len(payload[key]) > 4000:
            raise ValueError(f'{key} required, max 4000 characters')
    if payload.get('rights_confirmed') is not True:
        raise PermissionError('Rights confirmation required')
    settings = normalize_job_settings(payload.get('settings'))
    qc = normalize_qc(payload.get('qc_settings'))
    evaluation = payload.get('evaluation')
    if evaluation is not None:
        if (not isinstance(evaluation, dict) or set(evaluation) != {'cohort', 'variant'} or
                any(not isinstance(v, str) or not 1 <= len(v) <= 100 for v in evaluation.values())):
            raise ValueError('evaluation requires cohort and variant strings, max 100 characters')
    source_url = payload.get('source_url')
    if source_url:
        if payload.get('platform_permission') is not True:
            raise PermissionError('Platform permission required')
        source_url = normalize_youtube_url(source_url)
        path, name, fingerprint = None, source_url, None
    else:
        if upload is None or not filename:
            raise ValueError('Upload or source_url required')
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.mp4', '.mov', '.mkv', '.webm'}:
            raise ValueError('Unsupported media extension')
        path = store.INPUT / (uuid.uuid4().hex + suffix)
        try:
            with path.open('wb') as target:
                shutil.copyfileobj(upload, target)
            with path.open('rb') as content:
                fingerprint = hashlib.file_digest(content, 'sha256').hexdigest()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        name = Path(filename).name
    job = store.new_job(path, name, payload['creator'].strip(), payload['license_note'].strip(),
                        source_url=source_url, platform_permission=bool(source_url), settings=settings)
    job.update(qc_settings=qc, source_fingerprint=fingerprint, pipeline_version='quality-v2')
    if evaluation is not None:
        job['evaluation'] = evaluation
    store.save(job)
    return enqueue(job, queue)


def verify_reviewable(job: dict, index: int) -> bool:
    clip = job['candidates'][index]
    if clip.get('state') not in {'VALID', 'WARNING'} or not clip.get('file'):
        return False
    qc = inspect_candidate(Path(clip['file']), candidate_duration(clip),
                           job.get('audio_expected', True), normalize_qc(job.get('qc_settings')),
                           (720,1280) if (job.get('settings') or {}).get('render_quality') == 'high' else (540,960))
    return qc['state'] in {'VALID', 'WARNING'}


def review_job(jid: str, decisions: list, *, expected_revision: int) -> dict:
    with store.job_lock(jid):
        job = store.load(jid)
        if job['status'] not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'APPROVED', 'REJECTED'}:
            raise Conflict('Job is not ready for review')
        revision = len(job.get('decision_history', []))
        if type(expected_revision) is not int or revision != expected_revision:
            raise Conflict('Stale revision; reload job')
        if not isinstance(decisions, list) or not decisions:
            raise ValueError('At least one decision required')
        clean = [validate_decision(d, len(job['candidates'])) for d in decisions]
        indices = [d['candidate'] for d in clean]
        valid = {i for i, c in enumerate(job['candidates']) if c.get('state') in {'VALID', 'WARNING'}}
        if len(set(indices)) != len(indices) or set(indices) != valid:
            raise Conflict('Review must cover exactly the technically valid candidates')
        for d in clean:
            if d['decision'] == 'APPROVED' and not verify_reviewable(job, d['candidate']):
                raise Conflict('Artifact failed verification; request candidate QC/retry')
        event = {'revision': revision + 1, 'at': time.time(), 'decisions': clean,
                 'settings': job.get('settings'), 'qc_settings': job.get('qc_settings'),
                 'configuration': config_id(job),
                 'evaluation': job.get('evaluation'),
                 'windows': [{'start': c['start'], 'end': c['end']} for c in job['candidates']]}
        if not job.get('decision_history') and job.get('status') in {'APPROVED', 'REJECTED'}:
            job['legacy_decision'] = {'status': job['status'], 'approved': list(job.get('approved', [])),
                                      'note': 'Pre-history decision; dimensions and timestamp unknown'}
        job.setdefault('decision_history', []).append(event)
        job['approved'] = [d['candidate'] for d in clean if d['decision'] == 'APPROVED']
        # Partial failures remain visible after editorial decisions.
        job['status'] = ('PARTIAL_FAILED' if len(valid) != len(job['candidates']) else
                         'APPROVED' if job['approved'] else 'REJECTED')
        store.save(job)
        return job


def _append_editorial_event(job: dict, decisions: list, *, complete: bool, origin: str = 'ui', reason: str = '') -> None:
    if not job.get('decision_history') and job.get('status') in {'APPROVED', 'REJECTED'}:
        job['legacy_decision'] = {'status': job['status'], 'approved': list(job.get('approved', [])),
                                  'note': 'Pre-history decision; dimensions and timestamp unknown'}
    job.setdefault('decision_history', []).append({
        'revision': len(job.get('decision_history', [])) + 1, 'at': time.time(),
        'decisions': decisions, 'review_complete': complete, 'origin': origin, 'reason': reason,
        'settings': job.get('settings'), 'qc_settings': job.get('qc_settings'),
        'configuration': config_id(job), 'evaluation': job.get('evaluation'),
        'windows': [{'start': c.get('start'), 'end': c.get('end')} for c in job.get('candidates', [])]})


def review_candidate(jid: str, index: int, decision: str, reason: str, *, expected_revision: int,
                     ratings: dict | None = None, rework: bool = False, adjustments: str = '', origin: str = 'ui') -> dict:
    with store.job_lock(jid):
        job = store.load(jid)
        if job['status'] not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'}:
            raise Conflict('Job must be idle')
        history = job.get('decision_history', [])
        if type(expected_revision) is not int or len(history) != expected_revision:
            raise Conflict('Stale revision; reload job')
        value = validate_decision({'candidate': index, 'decision': decision, 'reason': reason,
                                   'rework': rework, 'adjustments': adjustments, **(ratings or {})}, len(job['candidates']))
        if decision == 'APPROVED' and not verify_reviewable(job, index):
            raise Conflict('Artifact must pass QC before approval')
        merged = current_decisions(job)
        merged[index] = value
        complete = len(merged) == len(job['candidates'])
        _append_editorial_event(job, [merged[i] for i in sorted(merged)], complete=complete, origin=origin)
        approved = set(job.get('approved', []))
        approved.discard(index)
        if decision == 'APPROVED':
            approved.add(index)
        job['approved'] = sorted(approved)
        failed = any(c.get('state') not in {'VALID', 'WARNING'} for c in job['candidates'])
        job['status'] = ('REJECTED' if complete and not approved else
                         'PARTIAL_FAILED' if failed else 'APPROVED' if complete else 'NEEDS_REVIEW')
        store.save(job)
        return job


def reject_job(jid: str, reason: str, *, origin: str = 'ui') -> dict:
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValueError('Informe um comentário para a recusa (até 4000 caracteres)')
    with store.job_lock(jid):
        job = store.load(jid)
        if job['status'] in {'QUEUED', 'DOWNLOADING', 'TRANSCRIBING', 'DIRECTING', 'RENDERING'}:
            raise Conflict('Job must be idle')
        decisions = [validate_decision({'candidate': i, 'decision': 'REJECTED', 'reason': reason,
                                        'rework': False, 'adjustments': ''}, len(job['candidates']))
                     for i in range(len(job.get('candidates', [])))]
        _append_editorial_event(job, decisions, complete=True, origin=origin, reason=reason)
        job.update(status='REJECTED', approved=[])
        store.save(job)
        return job


def retry_candidate(jid: str, index: int, *, queue=None) -> dict:
    with store.job_lock(jid):
        job = store.load(jid)
        if job['status'] not in {'FAILED', 'PARTIAL_FAILED', 'NEEDS_REVIEW'}:
            raise Conflict('Job must be idle')
        if type(index) is not int or not 0 <= index < len(job['candidates']):
            raise ValueError('Invalid candidate')
        clip = job['candidates'][index]
        if clip.get('state') in {'VALID', 'WARNING'}:
            raise Conflict('Valid result is preserved')
        if clip.get('state') != 'FAILED':
            raise Conflict('Verify existing artifacts before retry')
        if clip.get('attempts', 0) >= normalize_qc(job.get('qc_settings'))['max_attempts']:
            raise Conflict('Attempt limit exhausted')
        invalidate_approvals(job, {index})
        job.update(status='QUEUED', error=None, retry_candidate=index)
        store.save(job)
        return enqueue(job, queue)


def retry_enqueue(jid: str, *, queue=None) -> dict:
    with store.job_lock(jid):
        job = store.load(jid)
        if job['status'] != 'QUEUE_FAILED':
            raise Conflict('Only QUEUE_FAILED jobs may be re-enqueued')
        job.update(status='QUEUED', error=None)
        store.save(job)
        return enqueue(job, queue)


def verify_existing(jid: str) -> dict:
    """Add QC to existing outputs without rerendering or inventing editorial ratings."""
    with store.job_lock(jid):
        job = store.load(jid)
        if job['status'] not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'}:
            raise Conflict('Job must be idle')
        limits = job['qc_settings'] = normalize_qc(job.get('qc_settings'))
        for index, clip in enumerate(job.get('candidates', [])):
            target = store.OUTPUT / jid / f'candidate_{index+1}.mp4'
            qc = inspect_candidate(target, candidate_duration(clip), job.get('audio_expected', True), limits,
                                   (720,1280) if (job.get('settings') or {}).get('render_quality') == 'high' else (540,960))
            clip.update(qc=qc, state=qc['state'], file=str(target),
                        timeline_file=str(target.with_suffix('.timeline.json')))
        states = [c.get('state') for c in job.get('candidates', [])]
        if states and all(s in {'VALID', 'WARNING'} for s in states):
            if job['status'] not in {'APPROVED', 'REJECTED'}:
                job['status'] = 'NEEDS_REVIEW'
            job['error'] = None
        else:
            invalidate_approvals(job, {i for i, c in enumerate(job.get('candidates', []))
                                       if c.get('state') not in {'VALID', 'WARNING'}})
            job['status'] = 'PARTIAL_FAILED' if any(s in {'VALID', 'WARNING'} for s in states) else 'FAILED'
            job['error'] = 'Existing outputs failed QC; editorial approvals retained as history only'
        store.save(job)
        return job


def invalidate_approvals(job: dict, indices: set[int]) -> None:
    at=time.time()
    if 'candidate_review_invalidated_at' not in job:
        old=job.get('review_invalidated_at',0)
        last=job.get('decision_history',[])
        job['candidate_review_invalidated_at'] = ({str(i):old for i in range(len(job.get('candidates',[])))}
                                                  if old and last and last[-1]['at']<=old else {})
    job['candidate_review_invalidated_at'].update({str(i):at for i in indices})
    job['review_invalidated_at'] = at
    invalidated = sorted(set(job.get('approved', [])) & indices)
    if invalidated:
        job.setdefault('approval_invalidations', []).append({'at': time.time(), 'candidates': invalidated,
                                                            'reason': 'Artifact invalidated or replaced'})
        if not job.get('decision_history'):
            job['legacy_decision'] = {'status': job['status'], 'approved': list(job.get('approved', [])),
                                      'note': 'Pre-history decision; timestamp and ratings unknown'}
        job['approved'] = [i for i in job.get('approved', []) if i not in indices]
