"""Pure editorial v2 contracts. Never migrate or write a job during projection."""
from __future__ import annotations

import copy
from datetime import datetime
import math
import re
import uuid

from .editorial import current_decisions

DIMENSIONS = ('relevance', 'hook', 'context', 'narrative', 'proof', 'closure',
              'framing', 'captions', 'editing', 'technical_quality')
DECISIONS = ('PENDING', 'APPROVED', 'APPROVED_WITH_ADJUSTMENTS', 'REJECTED')
REASONS = ('IRRELEVANT_CONTENT', 'CREATOR_SELF_PROMOTION', 'WEAK_HOOK', 'MISSING_CONTEXT',
           'INCOMPLETE_PAYOFF', 'ABRUPT_ENDING', 'MISSING_DEMONSTRATION', 'BAD_FRAMING',
           'IMPORTANT_CONTENT_CROPPED', 'CAPTION_ERROR', 'GOOD_CONTENT_NEEDS_REWORK', 'TECHNICAL_FAILURE')
SEVERITIES = ('MINOR', 'MAJOR', 'CRITICAL', None)
DOMAINS = ('EDITORIAL', 'TECHNICAL', 'ADMINISTRATIVE', 'MIXED', 'UNSPECIFIED', None)
EDIT_TYPES = ('BOUNDARY_START', 'BOUNDARY_END', 'FRAMING', 'CAPTIONS', 'TITLE', 'EDITING', 'OTHER')
CHANNELS = ('streamlit', 'api', 'telegram')


def _object(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('Invalid object fields')


def _text(value, maximum=4000, *, nonempty=False):
    if not isinstance(value, str) or len(value) > maximum or (nonempty and not value.strip()):
        raise ValueError('Invalid text')


def _uuid(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError('Invalid UUID')
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError('Invalid UUID') from exc


def _integer(value, low, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError('Invalid integer')


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid nonnegative finite number')


def candidate_key(job_id: str, original_index: int) -> str:
    _uuid(job_id)
    _integer(original_index, 0)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'content-factory:{job_id}:{original_index}'))


def project_legacy_review(job: dict, index: int) -> dict:
    _integer(index, 0, len(job.get('candidates', [])) - 1)
    decision = current_decisions(job).get(index)
    if decision is None and job.get('editorial_protocol', 1) != 2 and not job.get('decision_history') and not job.get('review_invalidated_at') and not job.get('candidate_review_invalidated_at', {}).get(str(index)):
        legacy = job.get('legacy_decision') or job
        if legacy.get('status') in {'APPROVED', 'REJECTED'}:
            decision = {'decision': 'APPROVED' if index in legacy.get('approved', []) else 'REJECTED'}
    return {
        'candidate_id': job['candidates'][index].get('candidate_id') or candidate_key(job['id'], index),
        'original_index': index, 'legacy_decision': decision.get('decision') if decision else None,
        'comment_raw': decision.get('reason', '') if decision else '',
        'legacy_review': copy.deepcopy(decision),
        'normalized_decision': None if decision else 'PENDING',
        'qualification_status': 'UNCONFIRMED_LEGACY' if decision else 'NOT_REVIEWED',
        'dimensions': {key: None for key in DIMENSIONS},
        'content_grade': None,
    }


EVENT_FIELDS = ('schema_version', 'event_id', 'request_id', 'event_type', 'job_id', 'candidate_id',
                'candidate_version', 'render_revision', 'artifact_id', 'editorial_revision',
                'supersedes_event_id', 'actor', 'decision', 'rejection_domain', 'comment_raw',
                'reasons', 'dimensions', 'content_grade', 'relative_assessment', 'edit_requests',
                'review_timing', 'versions', 'created_at')


def validate_feedback_event(event: dict) -> dict:
    """Validate an immutable *human* event; return a detached copy with no invented ratings."""
    _object(event, EVENT_FIELDS, EVENT_FIELDS)
    if event['schema_version'] != '2.0' or event['event_type'] != 'REVIEW_SUBMITTED':
        raise ValueError('Unsupported feedback version/type')
    for key in ('event_id', 'request_id', 'job_id', 'candidate_id'):
        _uuid(event[key])
    if event['supersedes_event_id'] is not None:
        _uuid(event['supersedes_event_id'])
    for key in ('candidate_version', 'render_revision', 'editorial_revision'):
        _integer(event[key], 1)
    if not isinstance(event['artifact_id'], str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', event['artifact_id']):
        raise ValueError('Invalid artifact digest')
    actor = event['actor']
    _object(actor, ('kind', 'id', 'channel'), ('kind', 'id', 'channel'))
    if actor['kind'] != 'human' or actor['channel'] not in CHANNELS:
        raise ValueError('Human provenance required')
    _text(actor['id'], 200, nonempty=True)
    if event['decision'] not in DECISIONS[1:] or event['rejection_domain'] not in DOMAINS:
        raise ValueError('Invalid decision/domain')
    if event['decision'] == 'REJECTED' and event['rejection_domain'] is None:
        raise ValueError('Rejection domain required')
    if event['decision'] != 'REJECTED' and event['rejection_domain'] is not None:
        raise ValueError('Rejection domain only applies to rejection')
    _text(event['comment_raw'])
    dimensions = event['dimensions']
    _object(dimensions, DIMENSIONS)
    for value in dimensions.values():
        if value is not None:
            _integer(value, 1, 5)
    if event['content_grade'] is not None:
        _integer(event['content_grade'], 0, 3)
    for key in ('reasons', 'edit_requests'):
        if not isinstance(event[key], list) or len(event[key]) > 50:
            raise ValueError('Invalid feedback list')
    for reason in event['reasons']:
        _object(reason, ('code', 'severity', 'confirmed_by'), ('code', 'severity', 'confirmed_by'))
        if reason['code'] not in REASONS or reason['severity'] not in SEVERITIES or reason['confirmed_by'] != 'human':
            raise ValueError('Invalid confirmed reason')
    ids = set()
    for edit in event['edit_requests']:
        _object(edit, ('edit_id', 'type', 'status', 'comment', 'severity'), ('edit_id', 'type', 'status', 'comment'))
        _uuid(edit['edit_id'])
        if edit['edit_id'] in ids:
            raise ValueError('Duplicate edit ID')
        ids.add(edit['edit_id'])
        if edit['type'] not in EDIT_TYPES or edit['status'] not in ('OPEN', 'RESOLVED') or edit.get('severity') not in SEVERITIES:
            raise ValueError('Invalid edit request')
        _text(edit['comment'], nonempty=True)
    open_edits = [e for e in event['edit_requests'] if e['status'] == 'OPEN']
    if event['decision'] == 'APPROVED_WITH_ADJUSTMENTS' and not (event['comment_raw'].strip() or open_edits):
        raise ValueError('Describe adjustments')
    if event['decision'] == 'REJECTED' and not event['comment_raw'].strip():
        raise ValueError('Rejection comment required')
    if event['decision'] == 'APPROVED' and any(e.get('severity') in ('MAJOR', 'CRITICAL') for e in open_edits):
        raise ValueError('Clean approval has major pending edits')
    timing = event['review_timing']
    _object(timing, ('active_seconds', 'wall_seconds'), ('active_seconds', 'wall_seconds'))
    for value in timing.values():
        if value is not None:
            _finite(value)
    if all(timing[k] is not None for k in timing) and timing['active_seconds'] > timing['wall_seconds']:
        raise ValueError('Active review time exceeds wall time')
    versions = event['versions']
    _object(versions, ('brief_id', 'brief_sha256', 'component_snapshot_id'), ('brief_id', 'brief_sha256', 'component_snapshot_id'))
    for key, value in versions.items():
        _text(value, 200, nonempty=True)
        if key != 'brief_id' and value != 'UNKNOWN' and not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Invalid version hash')
    relative = event['relative_assessment']
    if relative is not None:
        fields = ('comparison_set_id', 'preferred_candidate_id', 'alternatives', 'all_options_below_bar', 'comment', 'confirmed_by')
        _object(relative, fields, fields)
        _uuid(relative['comparison_set_id'])
        _uuid(relative['preferred_candidate_id'])
        if not isinstance(relative['alternatives'], list) or not 1 <= len(relative['alternatives']) <= 6:
            raise ValueError('Relative alternatives required')
        for item in relative['alternatives']:
            _object(item, ('candidate_id', 'candidate_version','render_revision','artifact_id'), ('candidate_id', 'candidate_version'))
            _uuid(item['candidate_id'])
            _integer(item['candidate_version'], 1)
            if 'render_revision' in item or 'artifact_id' in item:
                _integer(item.get('render_revision'),1)
                if not isinstance(item.get('artifact_id'),str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',item['artifact_id']):
                    raise ValueError('Invalid frozen relative artifact')
        alternatives = [item['candidate_id'] for item in relative['alternatives']]
        if len(set(alternatives)) != len(alternatives) or relative['preferred_candidate_id'] not in alternatives:
            raise ValueError('Invalid relative pool')
        if type(relative['all_options_below_bar']) is not bool or relative['confirmed_by'] != 'human':
            raise ValueError('Relative human confirmation required')
        _text(relative['comment'])
    try:
        created = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
        if created.utcoffset() is None or created.utcoffset().total_seconds() != 0:
            raise ValueError('UTC timestamp required')
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError('Invalid UTC timestamp') from exc
    return copy.deepcopy(event)
