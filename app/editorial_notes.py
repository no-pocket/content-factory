"""Literal human observations without an inferred approval, rejection or rating."""
from __future__ import annotations
from datetime import datetime, timezone
import uuid

from . import store, service
from .artifacts import artifact_manifest, digest
from .editorial_contracts import candidate_key


def add_note(jid, cid, request, *, text, actor_id):
    if not isinstance(request, dict) or set(request) != {'request_id', 'expected_artifact_id'}:
        raise ValueError('Note requires request_id and exact artifact identity')
    ident = request['request_id']
    if not isinstance(ident, str) or str(uuid.UUID(ident)) != ident:
        raise ValueError('Invalid note request ID')
    if not isinstance(text, str) or not 0 < len(text.strip()) <= 4000:
        raise ValueError('Literal owner feedback required')
    fingerprint = digest({'candidate_id': cid, 'request': request, 'text': text, 'actor_id': actor_id})
    with store.job_lock(jid):
        job = store.load(jid)
        if job.get('editorial_protocol') != 2:
            raise service.Conflict('Notes require versioned candidates')
        notes = job.get('editorial_notes', [])
        receipt = next((n for n in notes if n['request_id'] == ident), None)
        if receipt:
            if receipt['request_sha256'] != fingerprint:
                raise service.Conflict('Note request ID reused with different content')
            return {'note': receipt}
        if job['status'] not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'}:
            raise service.Conflict('Job must be idle')
        index = next((i for i, c in enumerate(job['candidates']) if (c.get('candidate_id') or candidate_key(jid,i)) == cid), None)
        if index is None:
            raise ValueError('Unknown candidate')
        clip = job['candidates'][index]
        actual = 'sha256:' + digest(artifact_manifest(job, index))
        if request['expected_artifact_id'] != clip.get('artifact_id') or request['expected_artifact_id'] != actual:
            raise service.Conflict('Note refers to an outdated or changed render')
        event = {'event_type': 'COMMENT_ADDED', 'event_id': str(uuid.uuid4()), 'request_id': ident,
            'request_sha256': fingerprint, 'candidate_id': cid, 'artifact_id': actual,
            'candidate_version': clip['candidate_version'], 'render_revision': clip['render_revision'],
            'actor': {'kind': 'human', 'id': actor_id, 'channel': 'telegram'},
            'text': text, 'created_at': datetime.now(timezone.utc).isoformat()}
        job.setdefault('editorial_notes', []).append(event)
        store.save(job)
        return {'note': event}
