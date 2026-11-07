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


def _require_v1(job: dict) -> None:
    if job.get('editorial_protocol', 1) == 2:
        raise Conflict('editorial_protocol_required')


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
    if settings['framing_preset'] in {'web','tweet','document'} and not settings['framing_windows']:
        raise ValueError('Informe os intervalos da fonte em que a página/tweet aparece; fora deles o vídeo mantém o vertical aprovado')
    if settings['framing_windows'] and settings['framing_preset'] not in {'web','tweet','document'}:
        raise ValueError('Intervalos de evidência exigem preset de página, tweet ou documento')
    assembly = payload.get('assembly_plan')
    if assembly is not None:
        if not settings['timeline_v3']:
            raise ValueError('assembly_plan requires timeline_v3 opt-in')
        from .assembly import validate_assembly
        if not isinstance(assembly, dict) or assembly.get('schema_version') != '3.0':
            raise ValueError('assembly_plan requires schema 3.0')
        assembly = validate_assembly(assembly, assembly.get('source_duration'))
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
    if assembly is not None:
        job['assembly_plan'] = assembly
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
        _require_v1(job)
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
        _require_v1(job)
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
        _require_v1(job)
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
            target = (Path(clip['file']) if job.get('editorial_protocol') == 2 and clip.get('file') else
                      store.OUTPUT / jid / f'candidate_{index+1}.mp4')
            if not target.resolve().is_relative_to((store.OUTPUT / jid).resolve()):
                raise ValueError('Artifact outside job output directory')
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


def get_editorial_view(job: dict) -> dict:
    """Read-only candidate projection; never interpret legacy feedback as v2 labels."""
    from .editorial_contracts import DECISIONS, DIMENSIONS, candidate_key, project_legacy_review
    from .artifacts import artifact_manifest, digest
    rows = []
    for index, clip in enumerate(job.get('candidates', [])):
        row = project_legacy_review(job, index)
        cid = clip.get('candidate_id') or candidate_key(job['id'], index)
        artifact_id = clip.get('artifact_id')
        # Detect lost/replaced bytes even when the human event count did not change.
        intact = artifact_id is not None and artifact_id == 'sha256:' + digest(artifact_manifest(job, index))
        events = [e for e in job.get('feedback_events', []) if e['candidate_id'] == cid]
        current = next((e for e in reversed(events) if intact and e['artifact_id'] == artifact_id
                        and e['render_revision'] == clip.get('render_revision')
                        and e['candidate_version'] == clip.get('candidate_version')), None)
        if current and job.get('candidate_review_invalidated_at', {}).get(str(index)):
            from datetime import datetime
            if datetime.fromisoformat(current['created_at'].replace('Z', '+00:00')).timestamp() <= job['candidate_review_invalidated_at'][str(index)]:
                current = None
        if job.get('editorial_protocol') == 2:
            row.update(normalized_decision=current['decision'] if current else 'PENDING',
                       qualification_status='CONFIRMED_HUMAN' if current else 'NOT_REVIEWED',
                       dimensions=current['dimensions'] if current else {key: None for key in DIMENSIONS},
                       content_grade=current['content_grade'] if current else None,
                       comment_raw=current['comment_raw'] if current else '')
        row.update(candidate_id=cid, candidate_version=clip.get('candidate_version'),
                   render_revision=clip.get('render_revision'), artifact_id=artifact_id,
                   artifact_intact=intact, technical_state=clip.get('state', 'UNVERIFIED'),
                   edit_requests=current['edit_requests'] if current else [],
                   history=events, current_event=current)
        rows.append(row)
    counts = {key: sum(r['normalized_decision'] == key for r in rows) for key in DECISIONS}
    unknown = sum(r['normalized_decision'] is None for r in rows)
    reviewed = len(rows) - counts['PENDING'] - unknown
    return {'job_id': job['id'], 'editorial_protocol': job.get('editorial_protocol', 1),
            'editorial_revision': job.get('editorial_revision', 0), 'candidates': rows,
            'counts': {**counts, 'UNCONFIRMED_LEGACY': unknown},
            'review_status': 'COMPLETED' if rows and reviewed == len(rows) else 'PARTIAL' if reviewed else 'PENDING'}


def review_candidate_v2(jid: str, candidate_id: str, request: dict, *, channel: str = 'streamlit', actor_id: str = 'local-owner') -> dict:
    """One lock, one atomic JSON write: event, receipt and projections commit together."""
    from datetime import datetime, timezone
    from .artifacts import artifact_manifest, digest
    from .editorial_contracts import validate_feedback_event, candidate_key
    fields = {'request_id', 'expected_editorial_revision', 'expected_artifact_id', 'decision',
              'comment_raw', 'rejection_domain', 'reasons', 'dimensions', 'content_grade',
              'relative_assessment', 'edit_requests', 'review_timing'}
    required = {'request_id', 'expected_editorial_revision', 'expected_artifact_id', 'decision', 'comment_raw'}
    if not isinstance(request, dict) or set(request) - fields or required - set(request):
        raise ValueError('Invalid review request fields')
    if type(request['expected_editorial_revision']) is not int or request['expected_editorial_revision'] < 0:
        raise ValueError('Invalid editorial revision')
    try:
        if str(uuid.UUID(request['request_id'])) != request['request_id']:
            raise ValueError('Invalid request ID')
    except (TypeError, AttributeError) as exc:
        raise ValueError('Invalid request ID') from exc
    request_hash = digest({'candidate_id': candidate_id, 'request': request, 'channel': channel, 'actor_id': actor_id})
    with store.job_lock(jid):
        job = store.load(jid)
        if job.get('editorial_protocol', 1) != 2:
            raise Conflict('Job requires explicit editorial v2 opt-in')
        receipt = job.get('review_receipts', {}).get(request['request_id'])
        if receipt:
            if receipt['request_hash'] != request_hash:
                raise Conflict('Request ID reused with different content')
            return receipt['result']
        if job['status'] not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'}:
            raise Conflict('Job must be idle')
        revision = job.get('editorial_revision', 0)
        if request['expected_editorial_revision'] != revision:
            raise Conflict('Stale editorial revision; reload job')
        index = next((i for i, c in enumerate(job['candidates'])
                      if (c.get('candidate_id') or candidate_key(jid, i)) == candidate_id), None)
        if index is None:
            raise ValueError('Unknown candidate ID')
        clip = job['candidates'][index]
        expected = request['expected_artifact_id']
        actual = 'sha256:' + digest(artifact_manifest(job, index))
        if not expected or expected != clip.get('artifact_id') or expected != actual:
            raise Conflict('Stale or changed artifact; reload and verify render')
        if request['decision'] in {'APPROVED', 'APPROVED_WITH_ADJUSTMENTS'} and not verify_reviewable(job, index):
            raise Conflict('Artifact must pass QC before approval')
        previous = get_editorial_view(job)['candidates'][index]['current_event']
        versions = clip.get('editorial_versions') or job.get('editorial_versions') or {'brief_id': 'UNKNOWN', 'brief_sha256': 'UNKNOWN', 'component_snapshot_id': 'UNKNOWN'}
        event = validate_feedback_event({
            'schema_version': '2.0', 'event_type': 'REVIEW_SUBMITTED', 'event_id': str(uuid.uuid4()),
            'request_id': request['request_id'], 'job_id': jid, 'candidate_id': candidate_id,
            'candidate_version': clip['candidate_version'], 'render_revision': clip['render_revision'],
            'artifact_id': actual, 'editorial_revision': revision + 1,
            'supersedes_event_id': previous['event_id'] if previous else None,
            'actor': {'kind': 'human', 'id': actor_id, 'channel': channel},
            'decision': request['decision'], 'rejection_domain': request.get('rejection_domain'),
            'comment_raw': request['comment_raw'], 'reasons': request.get('reasons', []),
            'dimensions': request.get('dimensions', {}), 'content_grade': request.get('content_grade'),
            'relative_assessment': request.get('relative_assessment'), 'edit_requests': request.get('edit_requests', []),
            'review_timing': request.get('review_timing', {'active_seconds': None, 'wall_seconds': None}),
            'versions': versions, 'created_at': datetime.now(timezone.utc).isoformat(),
        })
        job.setdefault('feedback_events', []).append(event)
        job['editorial_revision'] = revision + 1
        view = get_editorial_view(job)
        # Compatibility list contains only clean approvals; adjusted approvals stay explicit.
        job['approved'] = [r['original_index'] for r in view['candidates'] if r['normalized_decision'] == 'APPROVED']
        if view['review_status'] == 'COMPLETED':
            job['status'] = 'APPROVED' if job['approved'] else 'REJECTED' if view['counts']['REJECTED'] == len(job['candidates']) else 'NEEDS_REVIEW'
        if any(c.get('state') not in {'VALID', 'WARNING'} for c in job['candidates']) and job['status'] != 'REJECTED':
            job['status'] = 'PARTIAL_FAILED'
        result = {'event': event, 'editorial_revision': revision + 1}
        job.setdefault('review_receipts', {})[request['request_id']] = {'request_hash': request_hash, 'result': result}
        store.save(job)
        return result
