"""Durable mapping of authenticated gateway acknowledgements to exact renders."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from . import store, service
from .artifacts import artifact_manifest, digest


def _key(chat_id, message_id):
    if (not isinstance(chat_id, str) or not re.fullmatch(r'-?[0-9]{1,20}', chat_id)
            or type(message_id) is not int or message_id < 1):
        raise ValueError('Invalid Telegram message identity')
    return digest({'chat_id': chat_id, 'message_id': message_id})


def lookup(chat_id, message_id):
    path = store.ROOT / 'telegram-deliveries' / (_key(chat_id, message_id) + '.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def list_deliveries(jid, cid):
    root = store.ROOT / 'telegram-deliveries'
    result = []
    for path in sorted(root.glob('*.json')):
        item = json.loads(path.read_text(encoding='utf-8'))
        if item['job_id'] == jid and item['candidate_id'] == cid:
            result.append(item)
    return result


def register(jid, cid, request):
    fields = {'artifact_id', 'master_sha256', 'chat_id', 'thread_id', 'message_id'}
    if not isinstance(request, dict) or not fields <= set(request) or set(request) - fields - {'sent_media'}:
        raise ValueError('Exact delivery acknowledgement required')
    media = request.get('sent_media')
    if media is not None:
        if (not isinstance(media, dict) or set(media) != {'width', 'height', 'duration', 'supports_streaming'}
                or any(type(media.get(k)) is not int or not 0 < media[k] <= 8192 for k in ('width', 'height'))
                or type(media.get('duration')) is not int or not 0 < media['duration'] <= 86400
                or type(media.get('supports_streaming')) is not bool):
            raise ValueError('Invalid Telegram acknowledged media metadata')
    for field, pattern in (('artifact_id', r'sha256:[0-9a-f]{64}'), ('master_sha256', r'[0-9a-f]{64}')):
        if not isinstance(request[field], str) or not re.fullmatch(pattern, request[field]):
            raise ValueError('Invalid delivery artifact checksum')
    key = _key(request['chat_id'], request['message_id'])
    if not isinstance(request['thread_id'], str) or not re.fullmatch(r'[0-9]{1,20}', request['thread_id']):
        raise ValueError('Invalid Telegram thread identity')
    root = store.ROOT / 'telegram-deliveries'
    root.mkdir(parents=True, exist_ok=True)
    with store.job_lock(jid):
        job = store.load(jid)
        clip = next((c for c in job['candidates'] if c.get('candidate_id') == cid), None)
        if clip is None:
            raise ValueError('Unknown candidate')
        identities = [clip, *clip.get('render_history', [])]
        identity = next((c for c in identities if c.get('artifact_id') == request['artifact_id']), None)
        manifest = identity.get('artifact_manifest') if identity else None
        if (not manifest or 'sha256:' + digest(manifest) != request['artifact_id']
                or request['master_sha256'] != (manifest.get('files', {}).get('mp4') or {}).get('sha256')):
            raise service.Conflict('Delivery does not match registered render bytes')
        item = {**request, 'sent_media': dict(media) if media is not None else None,
                'job_id': jid, 'candidate_id': cid,
                'candidate_version': identity['candidate_version'], 'render_revision': identity['render_revision']}
        with store.file_lock(root / 'index.lock'):
            existing = lookup(request['chat_id'], request['message_id'])
            if existing:
                if any(existing.get(k) != v for k, v in item.items()):
                    raise service.Conflict('Telegram message is already bound to another delivery')
                return existing
            item['recorded_at'] = datetime.now(timezone.utc).isoformat()
            path = root / (key + '.json')
            temporary = root / (key + '.' + uuid.uuid4().hex + '.tmp')
            try:
                temporary.write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return item
