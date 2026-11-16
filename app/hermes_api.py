"""Scoped private editorial API for the existing Hermes Telegram gateway."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
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


def _source_summary(source):
    fields = ('channel_id', 'name', 'status', 'rights_confirmed', 'platform_permission',
              'allowed_languages', 'allowed_video_kinds', 'allowed_model_scopes', 'revision')
    return {**{key: source[key] for key in fields if key in source},
            'authorization_confirmed': bool(source.get('authorization_reference') and
                source.get('rights_confirmed') is True and source.get('platform_permission') is True)}


def _external_allowed(job):
    snapshot = job.get('source_snapshot')
    if snapshot is None:
        return True  # Legacy jobs retain their existing explicit editorial access.
    if not isinstance(snapshot, dict) or 'external' not in snapshot.get('allowed_model_scopes', []):
        return False
    from .source_registry import get_source
    try:
        current = get_source(job.get('source_id') or snapshot.get('channel_id'))
    except (KeyError, ValueError, TypeError):
        return False
    return (current.get('status') == 'active' and current.get('rights_confirmed') is True
            and current.get('platform_permission') is True and bool(current.get('authorization_reference'))
            and 'external' in current.get('allowed_model_scopes', []))


def _require_external(job):
    if not _external_allowed(job):
        raise PermissionError('Source authorization does not permit external access; use the private application')


def _require_group_external(group):
    for job in group['jobs']:
        _require_external(store.load(job['id']))
    return group


def _candidate(jid, cid):
    job = store.load(jid)
    _require_external(job)
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
    public['social_captions'] = clip.get('social_captions', {})
    public['pace']=clip.get('pace')
    public['artifact_intact'] = bool(row['artifact_id'] and row['artifact_id'] == 'sha256:' + digest(manifest))
    public['master_sha256'] = (manifest['files'].get('mp4') or {}).get('sha256')
    from .media_delivery import get_delivery_metadata
    public['delivery_media'] = None
    public['delivery_media_error'] = None
    try:
        public['delivery_media'] = get_delivery_metadata(Path(clip['file']))
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as exc:
        public['delivery_media_error'] = type(exc).__name__
    public['notes'] = [n for n in job.get('editorial_notes', []) if n['candidate_id'] == cid and n['artifact_id'] == row['artifact_id']]
    public['historical_notes'] = [n for n in job.get('editorial_notes', []) if n['candidate_id'] == cid and n['artifact_id'] != row['artifact_id']]
    from .telegram_deliveries import list_deliveries
    public['deliveries'] = list_deliveries(jid, cid)
    public['application_url'] = os.getenv('CONTENT_FACTORY_PUBLIC_URL', 'http://localhost:8501').rstrip('/') + '/#revisao?' + urlencode({'job': jid})
    return job, row, public


def _pipeline(job):
    """Compact handoff: poll references, then inspect full transcript/media explicitly."""
    from .source_review import list_groups
    from .editorial_contracts import candidate_key
    jid = job['id']
    result = {key: job.get(key) for key in ('id', 'status', 'created_at', 'updated_at')}
    if not _external_allowed(job):
        return {**result, 'pipeline': {'ready': False, 'missing': ['external_source_authorization']}}
    group = next((g for g in list_groups() if any(j['id'] == jid for j in g['jobs'])), None)
    settings = job.get('settings') or {}
    result['parent_id']=job.get('source_parent_job') if job.get('editorial_rework') else None
    from .editorial_rework import enabled
    result['auto_rework_enabled']=enabled()
    result['reworks']=[{k:r.get(k) for k in ('child_id','state','error','review_revision')} for r in job.get('rework_requests',[])]
    runs = job.get('processing_runs', [])
    result['latest_run_id'] = runs[-1].get('run_id') if runs else None
    result['reprocess_available'] = job['status'] in ('FAILED','EDITORIAL_NO_CANDIDATES') and not job.get('candidates')
    editorial=job.get('editorial_request') or {}
    result['editorial']={'state':editorial.get('state'), 'reason':(editorial.get('plan') or {}).get('reason'),
                         'failure_code':editorial.get('failure_code'), 'fallback':job.get('editorial_planner_fallback')}
    if job['status'] in ('FAILED', 'PARTIAL_FAILED'):
        from collections import Counter
        events = [e for e in job.get('ai_events', []) if e.get('at', 0) >= (runs[-1].get('started_at', 0) if runs else 0)]
        rejected = Counter()
        for event in events:
            rejected.update(event.get('details', {}).get('rejections', {}))
        empty = job.get('failure_code') == 'NO_USABLE_CANDIDATES' or str(job.get('error', '')).startswith('No usable speech windows found')
        result['failure'] = {'code': 'NO_USABLE_CANDIDATES' if empty else 'PROCESSING_FAILED',
            'message': 'Nenhum corte passou nas validações; isso não significa ausência de fala.' if empty else 'Falha de processamento; consulte o diagnóstico na aplicação privada.',
            'proposal_rejections': dict(rejected),
            'incomplete_responses': sum(e['event'] == 'proposal_chunk_failed' and 'length' in e.get('details', {}).get('reason', '') for e in events)}
    transcript_exists = (store.JOBS / (jid + '.transcript.json')).is_file()
    idle = job['status'] in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED', 'EDITORIAL_NO_CANDIDATES'}
    candidates = []
    for index, clip in enumerate(job.get('candidates', [])):
        cid = clip.get('candidate_id') or candidate_key(jid, index)
        if idle:
            row = _candidate(jid, cid)[2]
        else:
            row = {'candidate_id': cid, 'technical_state': clip.get('state', 'PENDING'),
                   'artifact_id': clip.get('artifact_id'), 'artifact_intact': False}
        render_ready = bool(row.get('artifact_intact') and row['technical_state'] in ('VALID', 'WARNING'))
        row['renders'] = {'ready': render_ready, 'mp4': '/v2/hermes/jobs/' + jid + '/candidates/' + cid + '/media?' +
                          urlencode({'artifact_id': row['artifact_id']}) if render_ready else None,
                          'application_url': os.getenv('CONTENT_FACTORY_PUBLIC_URL', 'http://localhost:8501').rstrip('/') + '/#revisao?' + urlencode({'job': jid})}
        candidates.append(row)
    missing = ([] if transcript_exists else ['transcript']) + ([] if candidates else ['candidates'])
    if not idle:
        missing.append('processing')
    if not candidates or not all(c['renders']['ready'] for c in candidates):
        missing.append('renders')
    result.update(video_id=job.get('youtube_video_id') or (job.get('youtube_metadata') or {}).get('video_id'),
                  title=job.get('video_title') or job['original_name'], creator=job['creator'],
                  group_id=group['group_id'] if group else None,
                  model={'requested': {k: settings.get(k) for k in ('whisper_model', 'llm_model', 'llm_backend', 'ranker_mode', 'director_mode', 'render_engine')},
                         'resolved': {'ranker': job.get('ranker_used'), 'whisper': job.get('transcript_model') or job.get('model')}},
                  transcript={'available': transcript_exists, 'language': job.get('language'),
                              'endpoint': '/v2/hermes/jobs/' + jid + '/transcript'},
                  candidates=candidates, pipeline={'ready': not missing, 'missing': missing,
                    'next': 'editorial_no_candidates' if job['status']=='EDITORIAL_NO_CANDIDATES' else 'inspect_transcript_and_renders' if not missing else 'diagnose_failure' if job['status'] in ('FAILED', 'PARTIAL_FAILED', 'QUEUE_FAILED') else 'wait'},
                  application_url=os.getenv('CONTENT_FACTORY_PUBLIC_URL', 'http://localhost:8501').rstrip('/') + '/#revisao?' + urlencode({'job': jid}))
    return result


def dispatch(handler, path):
    method = handler.command
    editorial_actor = 'service:hermes-editorial-runner' if getattr(handler, 'editorial_worker', False) else None
    if path == ['editorial-requests'] and method == 'GET':
        import time
        editorial_actor or _actor()
        rows=[]
        for job in store.all_jobs():
            snapshot=job.get('source_snapshot')
            req=job.get('editorial_request')
            if (job.get('status') != 'WAITING_EDITORIAL_PLAN' or not isinstance(snapshot,dict)
                    or 'external' not in snapshot.get('allowed_model_scopes',[]) or not _external_allowed(job)
                    or not isinstance(req,dict) or req.get('state') not in ('REQUESTED','CLAIMED')
                    or req.get('generation_started') or req.get('expires_at',0) <= time.time()
                    or (req['state']=='CLAIMED' and req.get('lease_until',0)>time.time())):
                continue
            rows.append({'job_id':job['id'],'request_id':req['request_id'],'expires_at':req['expires_at']})
            if len(rows)>=100: break
        return handler._json(200, {'requests':rows})
    if len(path)==3 and path[0]=='jobs' and path[2] in ('editorial-claim','editorial-start') and method=='POST':
        import time
        from .editorial_requests import claim_job, begin_job_generation
        body=_body(handler)
        def authorize(job):
            snapshot=job.get('source_snapshot')
            if not isinstance(snapshot,dict) or 'external' not in snapshot.get('allowed_model_scopes',[]):
                raise PermissionError('External source authorization required')
            _require_external(job)
        if path[2]=='editorial-claim':
            if set(body) != {'request_id'}: raise ValueError('Invalid claim')
            # A 600-second model budget needs room for process shutdown and submission.
            result=claim_job(path[1],body['request_id'],actor=editorial_actor or _actor(),now=time.time(),seconds=750,authorize=authorize)
        else:
            if set(body) != {'request_id','token','version'}: raise ValueError('Invalid start')
            begin_job_generation(path[1],body['request_id'],actor=editorial_actor or _actor(),token=body['token'],version=body['version'],now=time.time(),authorize=authorize)
            result={'started':True}
        return handler._json(200,result)
    if len(path)==3 and path[0]=='jobs' and path[2]=='editorial-request' and method=='GET':
        from .editorial_plan import transcript_digest, segment_id
        editorial_actor or _actor()
        with store.job_lock(path[1]):
            job=store.load(path[1]); snapshot=job.get('source_snapshot'); req=job.get('editorial_request')
            if not isinstance(snapshot,dict) or 'external' not in snapshot.get('allowed_model_scopes',[]):
                raise PermissionError('External source authorization required')
            _require_external(job)
            if job.get('status') != 'WAITING_EDITORIAL_PLAN' or not isinstance(req,dict) or req.get('state') not in ('REQUESTED','CLAIMED'):
                raise ValueError('Editorial request unavailable')
            raw=(store.JOBS/(path[1]+'.transcript.json')).read_bytes()
            if len(raw)>4*1024*1024: raise ValueError('Transcript too large')
            tx=json.loads(raw.decode('utf8'))
            if transcript_digest(tx) != req.get('transcript_digest'): raise ValueError('Transcript changed')
            segments=[{'segment_id':segment_id(i),**{k:part.get(k) for k in ('start','end','text','words')}} for i,part in enumerate(tx['segments'])]
            keys=('request_id','editorial_attempt_id','job_id','run_id','source_fingerprint','duration_ms','transcript_digest','min_seconds','max_seconds','expires_at','layout_presets','subtitle_presets')
            return handler._json(200,{'request':{k:req.get(k) for k in keys},'transcript':{'language':tx.get('language'),'segments':segments}})
    if len(path)==3 and path[0]=='jobs' and path[2]=='editorial-failure' and method=='POST':
        import time
        from .editorial_requests import EditorialSourceDenied, fail_job_generation
        body=_body(handler)
        if set(body)!={'request_id','token','version','failure_code'}:
            raise ValueError('Invalid editorial failure report')
        def authorize(job):
            snapshot=job.get('source_snapshot')
            if not isinstance(snapshot,dict) or 'external' not in snapshot.get('allowed_model_scopes',[]):
                raise EditorialSourceDenied('External source authorization required')
            try: _require_external(job)
            except PermissionError as exc: raise EditorialSourceDenied('External source authorization revoked') from exc
        receipt=fail_job_generation(path[1],body['request_id'],actor=editorial_actor or _actor(),
            token=body['token'],version=body['version'],now=time.time(),failure_code=body['failure_code'],authorize=authorize)
        return handler._json(200,receipt)
    if len(path)==3 and path[0]=='jobs' and path[2]=='editorial-plan' and method=='POST':
        import time
        from .editorial_plan import parse_plan, MAX_PLAN_BYTES
        from .editorial_requests import EditorialSourceDenied, submit_job_plan
        if handler.headers.get_content_type() != 'application/json' or handler.headers.get('Transfer-Encoding'):
            raise ValueError('JSON with one Content-Length required')
        lengths=handler.headers.get_all('Content-Length',[])
        if len(lengths)!=1 or not 0 < int(lengths[0]) <= MAX_PLAN_BYTES:
            raise ValueError('Editorial body size invalid')
        raw=handler.rfile.read(int(lengths[0]))
        if len(raw)!=int(lengths[0]): raise ValueError('Incomplete editorial body')
        body=parse_plan(raw)
        if set(body)!={'token','version','plan'}: raise ValueError('Invalid editorial submission')
        def authorize(job):
            snapshot=job.get('source_snapshot')
            if not isinstance(snapshot,dict) or 'external' not in snapshot.get('allowed_model_scopes',[]):
                raise EditorialSourceDenied('External source authorization required')
            try: _require_external(job)
            except PermissionError as exc: raise EditorialSourceDenied('External source authorization revoked') from exc
        return handler._json(200,submit_job_plan(path[1],body['plan'],actor=editorial_actor or _actor(),token=body['token'],version=body['version'],now=time.time(),authorize=authorize))
    if len(path) == 3 and path[0] == 'deliveries' and method == 'GET':
        from .telegram_deliveries import lookup
        item = lookup(path[1], int(path[2]))
        if item is None:
            return handler._json(404, {'error': {'code': 'not_found', 'message': 'Unknown delivery'}})
        _require_external(store.load(item['job_id']))
        return handler._json(200, item)
    if path == ['sources'] and method == 'GET':
        from .source_registry import list_sources
        return handler._json(200, {'sources': [_source_summary(source) for source in list_sources()]})
    if len(path) == 2 and path[0] == 'sources' and method == 'GET':
        from .source_registry import get_source
        return handler._json(200, _source_summary(get_source(path[1])))
    if path == ['ingest'] and method == 'POST':
        from .source_ingestion import ingest_youtube
        body = _body(handler)
        request = dict(_intent(body, 'ingest'))
        if set(request) - {'source_url', 'source_id', 'settings'}:
            raise ValueError('Only source_url, source_id and settings may be supplied')
        settings = request.get('settings', {})
        if not isinstance(settings, dict) or settings.get('editorial_protocol', 2) != 2:
            raise ValueError('Hermes ingestion requires editorial_protocol=2')
        defaults = {'duration_mode': 'flexible', 'min_seconds': 8, 'target_seconds': 40, 'max_seconds': 180}
        planner_default = ({'editorial_planner': 'hermes_first'}
                           if os.getenv('CONTENT_FACTORY_HERMES_EDITORIAL_DEFAULT', '').lower() == 'true' else {})
        # Explicit classic uses its existing normalized limits; never inherit the flexible ceiling.
        request['settings'] = {**(defaults if settings.get('duration_mode', 'flexible') == 'flexible' else {}),
                               'auto_pace':True, **planner_default, **settings, 'editorial_protocol': 2}
        request.update(owner_message=body['owner_message'], actor_id=_actor())
        result = ingest_youtube(request)
        return handler._json(200 if result['duplicate'] else 201,
                             {'job': _pipeline(result['job']),
                              'duplicate': result['duplicate']})
    if len(path) == 2 and path[0] == 'jobs' and method == 'GET':
        job = store.load(path[1])
        return handler._json(200, _pipeline(job))
    if len(path) == 3 and path[0] == 'jobs' and path[2] == 'reprocess' and method == 'POST':
        job = store.load(path[1])
        _require_external(job)
        body = _body(handler)
        request = _intent(body, 'reprocess')
        result = service.reprocess_failed_job(path[1], request, owner_message=body['owner_message'], actor_id=_actor())
        return handler._json(200, _pipeline(result))
    if len(path) == 3 and path[0] == 'jobs' and path[2] == 'transcript' and method == 'GET':
        job = store.load(path[1])
        _require_external(job)
        transcript_path = store.JOBS / (path[1] + '.transcript.json')
        try:
            with transcript_path.open('rb') as source:
                raw = source.read(4 * 1024 * 1024 + 1)
        except OSError as exc:
            raise ValueError('Transcrição indisponível') from exc
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Transcrição excede o limite')
        transcript = json.loads(raw.decode('utf-8'))
        if not isinstance(transcript, dict):
            raise ValueError('Transcrição inválida')
        segments = transcript.get('segments')
        if not isinstance(segments, list) or any(not isinstance(s, dict) for s in segments):
            raise ValueError('Transcrição inválida')
        return handler._json(200, {'job_id': path[1], 'language': transcript.get('language'),
                                   'segments': [{k: s.get(k) for k in ('start', 'end', 'text')} for s in segments]})
    if path == ['groups'] and method == 'GET':
        from .source_review import list_groups
        return handler._json(200, {'groups': [g for g in list_groups()
            if all(_external_allowed(store.load(j['id'])) for j in g['jobs'])]})
    if len(path) in (2, 3) and path[0] == 'groups':
        from .source_review import get_group, select_finals
        if len(path) == 2 and method == 'GET':
            return handler._json(200, _require_group_external(get_group(path[1])))
        if len(path) == 3 and path[2] == 'selection' and method == 'POST':
            _require_group_external(get_group(path[1]))
            body = _body(handler)
            request = dict(_intent(body, 'selection'))
            if any(k in request for k in ('actor_id', 'channel')):
                raise ValueError('Actor is assigned by trusted bridge configuration')
            request.update(actor_id=_actor(), channel='telegram')
            request['comment_raw'] = body['owner_message']
            return handler._json(200, select_finals(path[1], request))
    if len(path) in (4, 5) and path[0] == 'jobs' and path[2] == 'candidates':
        jid, cid = path[1], path[3]
        _require_external(store.load(jid))
        if len(path) == 4 and method == 'GET':
            return handler._json(200, _candidate(jid, cid)[2])
        if len(path) == 5 and path[4] == 'captions' and method == 'POST':
            import uuid
            import time
            body = _body(handler)
            request = _intent(body, 'caption')
            if set(request) != {'request_id', 'expected_artifact_id', 'provider', 'text'}:
                raise ValueError('Invalid caption request')
            try:
                if str(uuid.UUID(request['request_id'])) != request['request_id']:
                    raise ValueError('Invalid request ID')
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Invalid request ID')
            provider, text = request['provider'], request['text']
            if provider not in ('instagram', 'facebook') or not isinstance(text, str) or not text.strip() or len(text) > 2200 or any(ord(c) < 32 and c not in '\n\r\t' for c in text):
                raise ValueError('Invalid caption')
            actor = _actor()
            with store.job_lock(jid):
                job, row, _ = _candidate(jid, cid)
                if not row['artifact_intact'] or row['artifact_id'] != request['expected_artifact_id']:
                    raise service.Conflict('Candidate artifact changed')
                clip = job['candidates'][row['original_index']]
                events = clip.setdefault('social_caption_events', [])
                existing = next((e for e in events if e['request_id'] == request['request_id']), None)
                value = {'text': text.strip(), 'origin': 'hermes', 'reason': None}
                if existing:
                    if (existing['provider'] != provider or existing['suggestion'] != value
                            or existing['owner_message'] != body['owner_message'] or existing['artifact_id'] != row['artifact_id']):
                        raise service.Conflict('Request ID already used')
                    return handler._json(200, existing['suggestion'])
                events.append({'request_id': request['request_id'], 'provider': provider, 'suggestion': value,
                               'artifact_id': row['artifact_id'], 'actor': actor, 'owner_message': body['owner_message'], 'created_at': time.time()})
                clip.setdefault('social_captions', {})[provider] = value
                store.save(job)
                return handler._json(200, value)
        if len(path) == 5 and path[4] == 'deliveries' and method == 'POST':
            from .telegram_deliveries import register
            body = _body(handler)
            if set(body) != {'delivery'}:
                raise ValueError('Delivery acknowledgement required')
            return handler._json(200, register(jid, cid, body['delivery']))
        if len(path) == 5 and path[4] == 'notes' and method == 'POST':
            from .editorial_notes import add_note
            body = _body(handler)
            request = _intent(body, 'note')
            return handler._json(200, add_note(jid, cid, request, text=body['owner_message'], actor_id=_actor()))
        if len(path) == 5 and path[4] == 'reviews' and method == 'POST':
            body = _body(handler)
            request = dict(_intent(body, 'review'))
            request['comment_raw'] = body['owner_message']
            if request.get('decision') == 'REJECTED':
                request.setdefault('rejection_domain', 'UNSPECIFIED')
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
