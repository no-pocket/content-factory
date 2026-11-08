"""Explicit operator rework of a reviewed artifact; never a fabricated QC failure."""
from __future__ import annotations

import copy
import time

from . import store
from .artifacts import artifact_manifest, digest
from .editorial_story import prepare_source_end_revision
from .service import Conflict, enqueue, invalidate_approvals


def request_render_revision(jid: str, index: int, transcript: dict, *, kind: str,
                                expected_artifact_id: str, expected_render_revision: int,
                                expected_candidate_version: int, expected_editorial_revision: int,
                                reason: str, assets: dict | None = None,
                                editorial_title: str | None = None, queue=None) -> dict:
    """Validate parent bindings under lock, snapshot history and dispatch one revision.

    Call only after operator authorization. A prepared replacement is PENDING,
    not FAILED; its render gets a fresh attempt budget and versioned output path.
    The old manifest stays available for register_render's version/history logic.
    """
    if kind not in {'source_end', 'media_sync'}:
        raise ValueError('Revision kind must be source_end or media_sync')
    if kind == 'media_sync' and editorial_title is not None:
        raise ValueError('Media sync revision must preserve the editorial title')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValueError('Revision reason required, max 4000 characters')
    with store.job_lock(jid):
        job = store.load(jid)
        if job.get('editorial_protocol') != 2:
            raise Conflict('Versioned editorial protocol required')
        if job.get('status') not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'APPROVED', 'REJECTED'}:
            raise Conflict('Job must be idle for an editorial revision')
        if type(index) is not int or not 0 <= index < len(job.get('candidates', [])):
            raise ValueError('Invalid candidate')
        clip = job['candidates'][index]
        if clip.get('state') not in {'VALID', 'WARNING'}:
            raise Conflict('Editorial revision requires an existing reviewed artifact')
        expected = {'artifact_id': expected_artifact_id, 'render_revision': expected_render_revision,
                    'candidate_version': expected_candidate_version}
        if (not isinstance(expected_artifact_id, str) or not expected_artifact_id
                or any(type(v) is not int or v < 1 for v in
                       (expected_render_revision, expected_candidate_version))
                or type(expected_editorial_revision) is not int
                or job.get('editorial_revision', 0) != expected_editorial_revision
                or any(clip.get(key) != value for key, value in expected.items())):
            raise Conflict('Stale revision parent; reload candidate and reviews')
        if not job.get('transcript_sha256') or digest(transcript) != job['transcript_sha256']:
            raise Conflict('Transcript does not match the saved source transcript')
        try:
            actual_artifact_id = 'sha256:' + digest(artifact_manifest(job, index))
        except (OSError, ValueError, KeyError) as exc:
            raise Conflict('Parent artifact cannot be verified from current files') from exc
        if actual_artifact_id != expected_artifact_id:
            raise Conflict('Parent artifact bytes or plan changed; reload and verify media')
        if kind == 'source_end':
            plan = prepare_source_end_revision(job, index, transcript, assets=assets,
                                               editorial_title=editorial_title)
        else:
            from .timeline import validate_timeline
            timeline = copy.deepcopy(clip.get('timeline'))
            if not isinstance(timeline, dict):
                raise Conflict('Media sync revision requires an existing validated timeline')
            validate_timeline(timeline)
            if (timeline.get('schema_version') != '2.0' or timeline.get('source_range') !=
                    {'start': clip['start'], 'end': clip['end']}):
                raise Conflict('Media sync revision requires an unchanged contiguous source timeline')
            plan = {'clip': {}, 'boundary': {'source_end': clip['end'],
                    'reason': 'media_sync_preserve_editorial_plan'}}
        job.setdefault('candidate_revision_history', []).append({
            'created_at': time.time(), 'reason': reason.strip(), 'origin': 'operator_render_revision',
            'kind': kind,
            'candidate_index': index, 'editorial_revision': expected_editorial_revision,
            'candidate': copy.deepcopy(clip), 'boundary': plan['boundary']})
        clip.update(plan['clip'])
        clip.update(state='PENDING', attempts=0, attempt_history=[])
        for key in (('model_story', 'qc') if kind == 'source_end' else ('qc',)):
            clip.pop(key, None)
        invalidate_approvals(job, {index})
        job.update(status='QUEUED', error=None, retry_candidate=index)
        store.save(job)
        return enqueue(job, queue)


def request_source_end_revision(jid: str, index: int, transcript: dict, **kwargs) -> dict:
    """Source-ending convenience entry point; guards are shared with media revisions."""
    return request_render_revision(jid, index, transcript, kind='source_end', **kwargs)
