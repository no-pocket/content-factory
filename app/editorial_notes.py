"""Literal human observations without an inferred approval, rejection or rating."""
from __future__ import annotations
from datetime import datetime, timezone
import uuid
import re

from . import store, service
from .artifacts import artifact_manifest, digest
from .editorial_contracts import candidate_key


def add_note(jid, cid, request, *, text, actor_id):
    if (not isinstance(request, dict) or set(request) - {'request_id', 'expected_artifact_id', 'source_message'}
            or not {'request_id', 'expected_artifact_id'} <= set(request)):
        raise ValueError('Note requires request_id and exact artifact identity')
    source = request.get('source_message')
    if source is not None:
        if not isinstance(source, dict) or set(source) != {'chat_id', 'thread_id', 'message_id', 'sent_at'}:
            raise ValueError('Invalid Telegram source message')
        if (not isinstance(source['chat_id'], str) or not re.fullmatch(r'-?[0-9]{1,20}', source['chat_id'])
                or not isinstance(source['thread_id'], str) or not re.fullmatch(r'[0-9]{1,20}', source['thread_id'])
                or type(source['message_id']) is not int or source['message_id'] < 1):
            raise ValueError('Invalid Telegram message identity')
        sent = datetime.fromisoformat(source['sent_at'])
        if sent.tzinfo is None:
            raise ValueError('Telegram message timestamp requires timezone')
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
        expected = request['expected_artifact_id']
        identity = clip
        if expected != clip.get('artifact_id') or expected != actual:
            identity = next((r for r in clip.get('render_history', [])
                if r.get('artifact_id') == expected and r.get('artifact_manifest')
                and 'sha256:' + digest(r['artifact_manifest']) == expected), None)
            if identity is None:
                raise service.Conflict('Note refers to an unknown or changed render')
        event = {'event_type': 'COMMENT_ADDED', 'event_id': str(uuid.uuid4()), 'request_id': ident,
            'request_sha256': fingerprint, 'candidate_id': cid, 'artifact_id': expected,
            'candidate_version': identity['candidate_version'], 'render_revision': identity['render_revision'],
            'actor': {'kind': 'human', 'id': actor_id, 'channel': 'telegram'},
            'text': text, 'created_at': datetime.now(timezone.utc).isoformat()}
        if source is not None:
            event['source_message'] = dict(source)
        job.setdefault('editorial_notes', []).append(event)
        store.save(job)
        return {'note': event}
