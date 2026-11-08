"""Scoped private editorial API for the existing Hermes Telegram gateway."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, urlencode, urlsplit

from . import service, store
from .artifacts import artifact_manifest, digest


def _body(handler):
    if handler.headers.get_content_type() != 'application/json' or handler.headers.get('Transfer-Encoding'):
        raise ValueError('JSON with one Content-Length required')
    lengths = handler.headers.get_all('Content-Length', [])
    if len(lengths) != 1 or not 0 < int(lengths[0]) <= 65536:
        raise ValueError('Body must be 1..65536 bytes')
    value = json.loads(handler.rfile.read(int(lengths[0])))
    if not isinstance(value, dict):
        raise ValueError('Object required')
    return value


def _actor():
    ident = os.getenv('CONTENT_FACTORY_HERMES_ACTOR_ID', '')
    if not re.fullmatch(r'[0-9]{1,20}', ident):
        raise RuntimeError('Configure the authorized Telegram owner before recording feedback')
    return 'telegram:' + ident


def _intent(body, fields):
    if set(body) != {'owner_message', fields}:
        raise ValueError('Explicit owner_message and action required')
    quote = body['owner_message']
    if not isinstance(quote, str) or not 0 < len(quote.strip()) <= 4000:
        raise ValueError('Quote the explicit owner instruction')
    if not isinstance(body[fields], dict):
        raise ValueError('Action must be an object')
    return body[fields]


def _candidate(jid, cid):
    job = store.load(jid)
    row = next((r for r in service.get_editorial_view(job)['candidates'] if r['candidate_id'] == cid), None)
    if row is None:
        raise ValueError('Unknown candidate')
    clip = job['candidates'][row['original_index']]
    manifest = artifact_manifest(job, row['original_index'])
    public = {key: row.get(key) for key in ('candidate_id', 'candidate_version', 'render_revision',
        'artifact_id', 'artifact_intact', 'normalized_decision', 'technical_state', 'dimensions',
        'content_grade', 'comment_raw', 'edit_requests')}
    public.update(job_id=jid, editorial_revision=job.get('editorial_revision', 0),
        title=clip.get('title') or clip.get('timeline', {}).get('hook', ''),
        transcript=clip.get('text', ''), start=clip.get('start'), end=clip.get('end'),
        model=job.get('comparison', {}).get('label') or job.get('settings', {}).get('llm_model'),
        director=clip.get('director_used'), renderer=clip.get('renderer_used'))
    public['artifact_intact'] = bool(row['artifact_id'] and row['artifact_id'] == 'sha256:' + digest(manifest))
    public['master_sha256'] = (manifest['files'].get('mp4') or {}).get('sha256')
    public['notes'] = [n for n in job.get('editorial_notes', []) if n['candidate_id'] == cid and n['artifact_id'] == row['artifact_id']]
    public['application_url'] = os.getenv('CONTENT_FACTORY_PUBLIC_URL', 'http://localhost:8501').rstrip('/') + '/?' + urlencode({'job': jid})
    return job, row, public


def dispatch(handler, path):
    method = handler.command
    if path == ['groups'] and method == 'GET':
        from .source_review import list_groups
        return handler._json(200, {'groups': list_groups()})
    if len(path) in (2, 3) and path[0] == 'groups':
        from .source_review import get_group, select_finals
        if len(path) == 2 and method == 'GET':
            return handler._json(200, get_group(path[1]))
        if len(path) == 3 and path[2] == 'selection' and method == 'POST':
            body = _body(handler)
            request = dict(_intent(body, 'selection'))
            if any(k in request for k in ('actor_id', 'channel')):
                raise ValueError('Actor is assigned by trusted bridge configuration')
            request.update(actor_id=_actor(), channel='telegram')
            request['comment_raw'] = body['owner_message']
            return handler._json(200, select_finals(path[1], request))
    if len(path) in (4, 5) and path[0] == 'jobs' and path[2] == 'candidates':
        jid, cid = path[1], path[3]
        if len(path) == 4 and method == 'GET':
            return handler._json(200, _candidate(jid, cid)[2])
        if len(path) == 5 and path[4] == 'notes' and method == 'POST':
            from .editorial_notes import add_note
            body = _body(handler)
            request = _intent(body, 'note')
            return handler._json(200, add_note(jid, cid, request, text=body['owner_message'], actor_id=_actor()))
        if len(path) == 5 and path[4] == 'reviews' and method == 'POST':
            body = _body(handler)
            request = dict(_intent(body, 'review'))
            request['comment_raw'] = body['owner_message']
            return handler._json(200, service.review_candidate_v2(jid, cid, request,
                channel='telegram', actor_id=_actor()))
        if len(path) == 5 and path[4] == 'media' and method == 'GET':
            with store.job_lock(jid):
                job, row, _ = _candidate(jid, cid)
                expected = parse_qs(urlsplit(handler.path).query).get('artifact_id', [None])[0]
                actual = 'sha256:' + digest(artifact_manifest(job, row['original_index']))
                if not row['artifact_intact'] or expected != actual or expected != row['artifact_id']:
                    raise service.Conflict('Media identity changed; inspect current candidate')
                if not service.verify_reviewable(job, row['original_index']):
                    raise service.Conflict('Current QC does not permit media delivery')
                target = Path(job['candidates'][row['original_index']]['file']).resolve()
                if not target.is_relative_to(store.OUTPUT.resolve()) or not target.is_file():
                    raise ValueError('Invalid media path')
                size = target.stat().st_size
                if not 0 < size <= 50_000_000:
                    raise ValueError('Use private application link; MP4 exceeds chat attachment limit')
                with target.open('rb') as stream:
                    handler.send_response(200)
                    handler.send_header('Content-Type', 'video/mp4')
                    handler.send_header('Content-Length', str(size))
                    handler.send_header('Cache-Control', 'no-store')
                    handler.end_headers()
                    shutil.copyfileobj(stream, handler.wfile)
                return
    return handler._json(404, {'error': {'code': 'not_found', 'message': 'Unknown Hermes editorial route'}})
