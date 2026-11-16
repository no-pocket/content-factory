"""Same-origin FastAPI adapter for the private React UI; domain rules stay shared."""
from __future__ import annotations

import hmac
import json
import math
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from . import service, store, source_registry, source_review, publication_schedule as agenda, publishing
from .artifacts import artifact_manifest, digest
from .editorial_contracts import candidate_key, DIMENSIONS, REASONS
from .job_settings import DEFAULTS, RANGES, normalize_job_settings, WHISPER_MODELS
from .quality import QC_DEFAULTS
from .version import VERSION
from .web_views import diagnostic, job_view, source_view, item_view, metrics_view

MAX_UPLOAD = 2 * 1024 ** 3


def token():
    value = os.getenv('CONTENT_FACTORY_WEB_TOKEN', '')
    filename = os.getenv('CONTENT_FACTORY_WEB_TOKEN_FILE')
    if not value and filename:
        value = Path(filename).read_text(encoding='ascii').strip()
    return value


@asynccontextmanager
async def lifespan(app):
    filename = os.getenv('CONTENT_FACTORY_WEB_TOKEN_FILE')
    if filename and not Path(filename).exists():
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='ascii') as handle:
            os.chmod(path, 0o600)
            handle.write(secrets.token_hex(32))
    if len(token()) < 24:
        raise RuntimeError('Configure a private web service token (24+ characters)')
    yield


app = FastAPI(title='Content Factory Web', version=VERSION, lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url='/api/openapi.json')


@app.middleware('http')
async def boundary(request: Request, call_next):
    supplied = request.headers.get('x-content-factory-web-token', '')
    try:
        expected = token()
    except OSError:
        expected = ''
    if len(expected) < 24 or not hmac.compare_digest(supplied, expected):
        return JSONResponse({'error': 'Acesso privado não autenticado.'}, status_code=401)
    hosts = {h.strip().lower() for h in os.getenv('CONTENT_FACTORY_WEB_HOSTS', 'localhost:8501,127.0.0.1:8501').split(',') if h.strip()}
    host = request.headers.get('host', '').lower()
    origin = request.headers.get('origin')
    if host not in hosts or request.headers.get('sec-fetch-site') == 'cross-site':
        return JSONResponse({'error': 'Origem não autorizada.'}, status_code=403)
    if origin and (urlsplit(origin).scheme not in ('http', 'https') or urlsplit(origin).netloc.lower() != host):
        return JSONResponse({'error': 'Origem não autorizada.'}, status_code=403)
    if request.method in ('POST', 'PUT', 'PATCH'):
        size = request.headers.get('content-length', '')
        limit = MAX_UPLOAD + 65536 if request.url.path in ('/api/jobs', '/api/assets') else 65536
        if not size.isdecimal() or int(size) > limit:
            return JSONResponse({'error': 'Corpo ausente ou acima do limite.'}, status_code=413)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(service.Conflict)
async def conflict_handler(request, exc):
    return JSONResponse({'error': diagnostic(str(exc)), 'code': 'conflict'}, status_code=409)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    return JSONResponse({'error': 'Formato de requisição inválido.'}, status_code=422)


async def domain_error(request, exc):
    code = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, FileNotFoundError) else 422
    return JSONResponse({'error': diagnostic(str(exc)) if code != 404 else 'Registro ou arquivo não encontrado.'}, status_code=code)


for exception in (ValueError, TypeError, KeyError, PermissionError, FileNotFoundError):
    app.add_exception_handler(exception, domain_error)


@app.exception_handler(Exception)
async def internal_error(request, exc):
    # Avoid logging arbitrary request content, persistence records or provider secrets.
    return JSONResponse({'error': 'Serviço indisponível. Consulte o diagnóstico local.'}, status_code=503)


def identity(jid, cid=None):
    if str(uuid.UUID(jid)) != jid:
        raise ValueError('ID de job inválido')
    job = store.load(jid)
    if cid is None:
        return job
    index = next((i for i, c in enumerate(job['candidates']) if (c.get('candidate_id') or candidate_key(jid, i)) == cid), None)
    if index is None:
        raise ValueError('Candidato desconhecido')
    return job, index


def youtube_enabled():
    return os.getenv('ENABLE_YOUTUBE_DOWNLOAD', 'true').lower() == 'true'


@app.get('/api/settings')
def settings():
    defaults = {**DEFAULTS, 'auto_pace':True, 'editorial_protocol': 2, 'llm_backend': 'kepler_gpu',
                'render_fallback_ffmpeg': os.getenv('RENDER_FALLBACK_FFMPEG', 'true').lower() == 'true'}
    if os.getenv('CONTENT_FACTORY_HERMES_EDITORIAL_DEFAULT', '').lower() == 'true':
        defaults['editorial_planner']='hermes_first'
    return {'defaults': defaults, 'ranges': RANGES, 'qc_defaults': QC_DEFAULTS,
            'whisper_models': sorted(WHISPER_MODELS), 'dimensions': list(DIMENSIONS), 'reasons': list(REASONS),
            'youtube_enabled': youtube_enabled(), 'max_upload_bytes': MAX_UPLOAD, 'release': VERSION}


def assets():
    from .edit_render import read_assets
    return [{'id': k, 'd': v['description'], 'duration': v['duration'], 't': f"{v['duration']:.0f} s",
             'license': v.get('license_note', '')} for k, v in read_assets().items()]


def drafts():
    if not publishing.ROOT.exists():
        return []
    result = []
    for path in publishing.ROOT.glob('*.json'):
        r = json.loads(path.read_text(encoding='utf-8'))
        d = r['draft']
        result.append({'id': r['draft_id'], 'at': r['created_at'] * 1000, 'pv': d['provider'],
                       'cand': d['candidate_id'], 'job_id': d['job_id'], 'artifact': d['artifact_id'],
                       'title': d['title'], 'desc': d['description']})
    return sorted(result, key=lambda r: r['at'], reverse=True)


def provider_status():
    online = agenda.worker_online()
    mode = os.getenv('CONTENT_FACTORY_META_ENABLED', 'auto').lower()
    enabled = mode == 'true' or (mode == 'auto' and agenda.configured())
    return {p: {'state': 'CONFIGURED_UNVERIFIED' if p in ('instagram', 'facebook') and enabled else 'NOT_CONFIGURED',
                'can_schedule': p in ('instagram', 'facebook') and enabled,
                'worker_online': online if p in ('instagram', 'facebook') else False,
                'title_limit': 100 if p == 'youtube' else 255,
                'caption_limit': 5000 if p == 'youtube' else 2200}
            for p in ('instagram', 'facebook', 'youtube', 'tiktok')}


def destinations():
    # Previously confirmed destinations, not arbitrary credential/config contents.
    result = {}
    for item in agenda.list_items():
        if item['state'] != 'PUBLISHED' or item['draft']['provider'] not in ('instagram', 'facebook'):
            continue
        d = item.get('destination') or {}
        provider = item['draft']['provider']
        if not str(d.get('page_id', '')).isdecimal() or (provider == 'instagram' and not str(d.get('instagram_id', '')).isdecimal()):
            continue
        key = provider + ':' + d['page_id'] + ':' + str(d.get('instagram_id') or '')
        result[key] = {'id': key, 'pv': provider, 'page_id': d['page_id'], 'instagram_id': d.get('instagram_id'),
                       'label': provider.capitalize() + ' — destino já utilizado'}
    return list(result.values())


@app.get('/api/bootstrap')
def bootstrap():
    return {'jobs': [job_view(j) for j in store.all_jobs()], 'sources': [source_view(r) for r in source_registry.list_sources()],
            'assets': assets(), 'agenda': [item_view(r) for r in agenda.list_items()], 'drafts': drafts(),
            'providers': provider_status(), 'destinations': destinations(), 'release': VERSION}


@app.get('/api/jobs/{jid}')
def get_job(jid: str):
    return job_view(identity(jid))


async def upload_request(request):
    """Multipart spools large files to disk; domain copy never buffers the entire video."""
    if request.headers.get('content-type', '').startswith('multipart/form-data'):
        form = await request.form(max_files=1, max_fields=1, max_part_size=65536)
        try:
            raw = form.get('metadata')
            if not isinstance(raw, str) or len(raw.encode()) > 65536:
                raise ValueError('Metadados inválidos')
            data = json.loads(raw)
            file = form.get('file')
            if not isinstance(file, UploadFile) or not file.size or file.size > MAX_UPLOAD:
                raise ValueError('Arquivo vazio ou acima de 2 GiB')
            return data, file, form
        except Exception:
            await form.close()
            raise
    if int(request.headers.get('content-length', '0')) > 65536:
        raise ValueError('Metadados acima do limite')
    data = await request.json()
    return data, None, None


@app.post('/api/jobs', status_code=201)
async def add_job(request: Request):
    data, file, form = await upload_request(request)
    try:
        allowed = {'creator', 'video_title', 'license_note', 'rights_confirmed', 'platform_permission', 'source_url', 'settings', 'qc_settings', 'assembly_plan'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError('Campos de job inválidos')
        if data.get('source_url') and (file or not youtube_enabled()):
            raise PermissionError('Download YouTube desabilitado ou origem duplicada')
        overrides = data.get('settings') or {}
        effective = {**settings()['defaults'], **overrides}
        if overrides.get('editorial_protocol') == 1 and 'editorial_planner' not in overrides:
            effective['editorial_planner']='local'
        if effective['duration_mode'] == 'flexible':
            for k, v in (('min_seconds', 8), ('max_seconds', 180)):
                if k not in overrides:
                    effective[k] = v
        data['settings'] = normalize_job_settings(effective)
        if data['settings']['editorial_planner']=='hermes_first' and data.get('assembly_plan') is not None:
            raise ValueError('Montagem manual requer planejamento local; selecione o modo local')
        if data.get('source_url'):
            from .source_ingestion import public_metadata, find_existing_youtube, recover_import_enqueue
            if data.get('rights_confirmed') is not True or data.get('platform_permission') is not True:
                raise PermissionError('Confirme direitos e autorização da plataforma')
            metadata = await run_in_threadpool(public_metadata, data['source_url'])
            data['source_url'] = metadata['source_url']
            def create_url_job():
                with store.file_lock(store.ROOT / 'source-ingestion.lock'):
                    with store.file_lock(store.ROOT / 'sources.lock'):
                        try:
                            source_registry.get_source(metadata['channel_id'])
                        except KeyError:
                            # Keep the existence check and manual creation atomic
                            # against registration/revocation of this channel.
                            existing = find_existing_youtube(metadata['video_id'])
                            if existing:
                                if existing['status'] in ('QUEUED', 'QUEUE_FAILED'):
                                    existing = recover_import_enqueue(existing['id'])
                                return existing, True
                            provenance = {'youtube_metadata': metadata, 'video_title': metadata['title'], 'original_name': metadata['title']}
                            return service.create_job(data, source_provenance=provenance), False
                        return None
            manual = await run_in_threadpool(create_url_job)
            if manual is None:
                # This function reacquires the same locks and revalidates source
                # rights and metadata; never nest the file locks.
                from .source_ingestion import ingest_youtube
                details={key:data[key] for key in ('creator','license_note','video_title','qc_settings','assembly_plan') if key in data}
                result = await run_in_threadpool(ingest_youtube, {
                    'source_url':data['source_url'], 'source_id':metadata['channel_id'],
                    'settings':data['settings']}, job_details=details)
                return JSONResponse({**job_view(result['job']), 'duplicate':result['duplicate']},
                                    status_code=200 if result['duplicate'] else 201)
            job, duplicate = manual
            return JSONResponse({**job_view(job), 'duplicate': duplicate}, status_code=200 if duplicate else 201)
        job = await run_in_threadpool(service.create_job, data, upload=file.file if file else None, filename=file.filename if file else None)
        return job_view(job)
    finally:
        if form is not None:
            await form.close()


@app.post('/api/youtube/metadata')
def youtube_metadata(body: dict):
    from .source_ingestion import public_metadata
    if set(body) != {'source_url'}:
        raise ValueError('Informe apenas source_url')
    try:
        return public_metadata(body['source_url'])
    except (ValueError, PermissionError):
        raise
    except Exception as exc:
        raise HTTPException(422, detail='Não foi possível consultar o vídeo público no YouTube.') from exc


@app.post('/api/assets', status_code=201)
async def add_asset(request: Request):
    from .asset_library import register_asset
    data, file, form = await upload_request(request)
    try:
        if not isinstance(data, dict) or set(data) != {'description', 'license_note', 'rights_confirmed'} or data['rights_confirmed'] is not True:
            raise PermissionError('Descrição, licença e confirmação de direitos obrigatórias')
        if file is None or file.size > 300_000_000:
            raise ValueError('Asset deve ter até 300 MB')
        # Serialize catalog read/replace across web processes.
        def register():
            with store.file_lock(store.ROOT / '.asset-catalog.lock'):
                return register_asset(file.file, file.filename, data['description'], data['license_note'])
        r = await run_in_threadpool(register)
        return {'id': r['asset_id'], 'd': r['description'], 'duration': r['duration'], 'license': r['license_note']}
    finally:
        if form is not None:
            await form.close()


@app.post('/api/jobs/{jid}/candidates/{cid}/review')
def review(jid: str, cid: str, body: dict):
    job, index = identity(jid, cid)
    if set(body) != {'seen', 'p', 'request_id'}:
        raise ValueError('Contrato de revisão inválido')
    seen, p = body['seen'], body['p']
    if not isinstance(seen, dict) or set(seen) != {'artifact', 'n', 'revision'} or not isinstance(p, dict):
        raise ValueError('Identidade de revisão inválida')
    if set(p) != {'dec', 'comment', 'reasons', 'adjust', 'rating', 'grade'}:
        raise ValueError('Campos de avaliação inválidos')
    if job.get('editorial_protocol') == 2:
        request = {'request_id': body['request_id'], 'expected_editorial_revision': seen['revision'],
                   'expected_artifact_id': seen['artifact'], 'decision': 'APPROVED_WITH_ADJUSTMENTS' if p['dec'] == 'ADJ' else p['dec'],
                   'comment_raw': p['comment'], 'rejection_domain': 'UNSPECIFIED' if p['dec'] == 'REJECTED' else None,
                   'reasons': [{'code': code, 'severity': None, 'confirmed_by': 'human'} for code in p['reasons']],
                   'dimensions': p['rating'], 'content_grade': p['grade'],
                   'edit_requests': [{'edit_id': str(uuid.uuid5(uuid.UUID(body['request_id']), 'adjustment')), 'type': 'OTHER',
                                      'status': 'OPEN', 'comment': p['adjust'], 'severity': 'MINOR'}] if p['adjust'] else []}
        service.review_candidate_v2(jid, cid, request, channel='api', expected_candidate_history=seen['n'])
    else:
        if p['dec'] not in ('APPROVED', 'REJECTED') or p['grade'] is not None:
            raise ValueError('Protocolo legado não aceita ajustes/grau; não há migração automática')
        if any(k not in ('hook', 'context', 'closure', 'captions') and v is not None for k, v in p['rating'].items()):
            raise ValueError('Dimensão indisponível no protocolo legado')
        service.review_candidate(jid, index, p['dec'], p['comment'], expected_revision=seen['revision'], ratings=p['rating'],
                                 rework=bool(p['adjust']), adjustments=p['adjust'], origin='api',
                                 expected_artifact_id=seen['artifact'], expected_candidate_history=seen['n'])
    return job_view(store.load(jid))


@app.post('/api/jobs/{jid}/{action}')
def job_action(jid: str, action: str, body: dict):
    identity(jid)
    if action == 'verify':
        job = service.verify_existing(jid)
    elif action == 'retry-enqueue':
        job = service.retry_enqueue(jid)
    elif action == 'retry-editorial':
        job = service.reprocess_failed_job(jid, body, owner_message='Solicitada nova análise editorial.', actor_id='browser:owner')
    elif action == 'reject':
        job = service.reject_job(jid, body.get('reason'), origin='api')
    else:
        raise HTTPException(404)
    return job_view(job)


@app.post('/api/jobs/{jid}/candidates/{cid}/{action}')
def candidate_action(jid: str, cid: str, action: str, body: dict):
    job, index = identity(jid, cid)
    if action == 'confirm-boundary':
        if set(body) != {'artifact'} or not isinstance(body['artifact'], str):
            raise ValueError('Identidade do render obrigatória')
        service.confirm_audio_boundary(jid, cid, expected_artifact_id=body['artifact'], actor_id='local-owner', boundary='both')
        return job_view(store.load(jid))
    if action == 'retry':
        return job_view(service.retry_candidate(jid, index))
    if action == 'captions':
        from .social_captions import regenerate
        regenerate(jid, cid, body.get('artifact') if job.get('editorial_protocol') == 2 else None)
        return job_view(store.load(jid))
    if action in ('edit', 'frames'):
        expected_fields = ({'artifact', 'candidate_version', 'render_revision'} if action == 'frames' else
                           {'artifact', 'candidate_version', 'render_revision', 'editorial_revision',
                            'request_id', 'changes'})
        if set(body) != expected_fields:
            raise ValueError('Invalid frame analysis request' if action == 'frames' else 'Invalid timeline edit request')
        clip = job['candidates'][index]
        if job.get('editorial_protocol') != 2 or clip.get('state') not in ('VALID', 'WARNING'):
            raise service.Conflict('A verified protocol 2 candidate is required')
        if job.get('status') not in ('NEEDS_REVIEW', 'PARTIAL_FAILED', 'APPROVED', 'REJECTED'):
            raise service.Conflict('Job must be idle before frame analysis or editing')
        expected = {
            'artifact_id': body.get('artifact'),
            'candidate_version': body.get('candidate_version'),
            'render_revision': body.get('render_revision'),
        }
        if (any(type(expected[key]) is not int or expected[key] < 1
                for key in ('candidate_version', 'render_revision'))
                or expected['artifact_id'] != clip.get('artifact_id')
                or expected['candidate_version'] != clip.get('candidate_version')
                or expected['render_revision'] != clip.get('render_revision')):
            raise service.Conflict('Candidate changed; reload before editing')
        actual = 'sha256:' + digest(artifact_manifest(job, index))
        if actual != clip.get('artifact_id'):
            raise service.Conflict('Candidate artifact changed; verify it before editing')
        if action == 'frames':
            source = Path(job.get('source') or '').resolve()
            if not source.is_relative_to(store.INPUT.resolve()) or not source.is_file():
                raise service.Conflict('Authorized source media is unavailable')
            from .frame_analysis import analyze_candidate_frames
            return analyze_candidate_frames(source, clip.get('timeline') or {})
        transcript_path = store.JOBS / f'{jid}.transcript.json'
        if not transcript_path.is_file():
            raise service.Conflict('Saved source transcript is unavailable')
        transcript = json.loads(transcript_path.read_text(encoding='utf-8'))
        from .editorial_revisions import request_render_revision
        revised = request_render_revision(
            jid, index, transcript, kind='timeline_edit',
            expected_artifact_id=body['artifact'],
            expected_render_revision=body['render_revision'],
            expected_candidate_version=body['candidate_version'],
            expected_editorial_revision=body['editorial_revision'],
            reason='Human-reviewed timeline edit', changes=body['changes'],
            request_id=body['request_id'],
        )
        return job_view(revised)
    raise HTTPException(404)


@app.api_route('/api/jobs/{jid}/candidates/{cid}/media/{kind}', methods=['GET', 'HEAD'])
def media(jid: str, cid: str, kind: str, artifact: str | None = None, download: bool = False):
    job, index = identity(jid, cid)
    if kind not in ('mp4', 'webm', 'timeline'):
        raise ValueError('Formato inválido')
    if job['status'] not in ('NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'):
        raise service.Conflict('Job em processamento')
    manifest = artifact_manifest(job, index, presentation_cache=True)
    actual = 'sha256:' + digest(manifest)
    registered = job['candidates'][index].get('artifact_id')
    if (registered and actual != registered) or (artifact is not None and artifact != (registered or actual)):
        raise service.Conflict('Artefato mudou; recarregue e verifique o vídeo')
    if job['candidates'][index].get('state') not in ('VALID', 'WARNING'):
        raise service.Conflict('Candidato exige verificação técnica')
    part = manifest['files'].get(kind)
    if not part:
        raise FileNotFoundError()
    root = (store.OUTPUT / jid).resolve()
    path = (root / part['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Arquivo fora do job')
    mime = {'mp4': 'video/mp4', 'webm': 'video/webm', 'timeline': 'application/json'}[kind]
    return FileResponse(path, media_type=mime, filename=path.name if download or kind == 'timeline' else None,
                        content_disposition_type='attachment' if download or kind == 'timeline' else 'inline')


@app.put('/api/sources/{sid}')
def save_source(sid: str, body: dict):
    r = body['r']
    if r['id'] != sid:
        raise ValueError('Canal inconsistente')
    data = {'channel_id': sid, 'name': r['name'], 'status': r['status'], 'authorization_reference': r['ref'],
            'rights_confirmed': r['rights'], 'platform_permission': r['platform'], 'allowed_languages': r['langs'].split(',') if r['langs'] else [],
            'allowed_video_kinds': r['kinds'], 'allowed_model_scopes': r['scopes']}
    try:
        return source_view(source_registry.upsert_source(data, expected_revision=body['expectedRev']))
    except ValueError as exc:
        if str(exc) == 'Stale source revision':
            raise service.Conflict('Este cadastro mudou; atualize antes de salvar') from exc
        raise


@app.get('/api/groups')
def groups():
    return diagnostic(source_review.list_groups())


@app.get('/api/groups/{gid}')
def group(gid: str):
    return diagnostic(source_review.get_group(gid))


@app.post('/api/groups/{gid}/finals')
def select_finals(gid: str, body: dict):
    return diagnostic(source_review.select_finals(gid, {**body, 'actor_id': 'local-owner', 'channel': 'api'}))


@app.get('/api/doctor')
def doctor():
    from .doctor import snapshot
    connection = store.rconn()
    result = diagnostic(snapshot(connection))
    try:
        result.update(queue=connection.llen('clips:queue'), processing=connection.llen('clips:processing'))
    except Exception:
        result.update(queue=None, processing=None)
    return {**result, 'release': VERSION, 'agenda_online': agenda.worker_online()}


@app.get('/api/metrics')
def metrics():
    return metrics_view(store.all_jobs())


@app.post('/api/publications/drafts')
def save_draft(body: dict):
    identity(body['job_id'], body['cand'])
    if not isinstance(body.get('artifact'), str) or not body['artifact']:
        raise ValueError('Identidade do artefato obrigatória')
    item = publishing.queue_dry_run(body['job_id'], body['cand'], body['pv'], title=body['title'], description=body.get('desc', ''), expected_artifact_id=body['artifact'])
    return {'id': item['draft_id'], 'state': 'DRY_RUN'}


@app.post('/api/publications/schedule')
def schedule(body: dict):
    if set(body) != {'rows', 'immediate'} or type(body['immediate']) is not bool:
        raise ValueError('Agendamento inválido')
    if not isinstance(body['rows'], list) or len(body['rows']) != 1:
        raise ValueError('Agende um item por envio')
    r = body['rows'][0]
    required = {'pv', 't', 'at', 'job_id', 'candidate_id', 'artifact', 'page_id'}
    if not isinstance(r, dict) or required - set(r):
        raise ValueError('Identidade do candidato e destino obrigatórios')
    at = r['at']
    if type(at) not in (int, float) or not math.isfinite(at) or (not body['immediate'] and at <= time.time() * 1000):
        raise ValueError('Escolha um horário futuro')
    if r['pv'] not in ('instagram', 'facebook'):
        raise ValueError('Provedor disponível somente para rascunhos locais')
    job, index = identity(r['job_id'], r['candidate_id'])
    if r['artifact'] != job['candidates'][index].get('artifact_id'):
        raise service.Conflict('Artefato de publicação mudou')
    # Local preflight before checking configuration: unapproved input never becomes an intention.
    publishing.build_draft(job, r['candidate_id'], r['pv'], title=r['t'], description=r.get('caption', ''))
    if not provider_status()[r['pv']]['can_schedule']:
        raise service.Conflict('Integração não configurada para envio. Salve um rascunho local.')
    item = agenda.schedule(r['job_id'], r['candidate_id'], r['pv'], title=r['t'], caption=r.get('caption', ''),
                          scheduled_at=time.time() if body['immediate'] else at / 1000,
                          page_id=r['page_id'], instagram_id=r.get('instagram_id'), timezone_name='America/Sao_Paulo', expected_artifact_id=r['artifact'])
    return item_view(item)


@app.post('/api/publications/{pid}/reschedule')
def reschedule(pid: str, body: dict):
    at = body['at']
    if type(at) not in (int, float) or not math.isfinite(at) or at <= time.time() * 1000:
        raise ValueError('Escolha um horário futuro')
    try:
        return item_view(agenda.reschedule(pid, at / 1000, 'America/Sao_Paulo'))
    except ValueError as exc:
        if 'pending' in str(exc):
            raise service.Conflict('O envio já começou; não pode ser reagendado') from exc
        raise


@app.post('/api/publications/{pid}/cancel')
def cancel(pid: str, body: dict):
    try:
        return item_view(agenda.cancel(pid))
    except ValueError as exc:
        if 'pending' in str(exc):
            raise service.Conflict('O envio já começou; não pode ser cancelado') from exc
        raise


@app.post('/api/publications/{pid}/retry')
def retry_publication(pid: str, body: dict):
    if set(body) != {'confirmed_not_published'} or body['confirmed_not_published'] is not True:
        raise ValueError('Confirma\u00e7\u00e3o obrigat\u00f3ria')
    return item_view(agenda.retry(pid, confirmed_not_published=True))
