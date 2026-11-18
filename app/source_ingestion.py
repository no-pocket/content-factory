"""Explicit, authorized URL ingestion; never monitors channels or publishes results."""
from __future__ import annotations

import os
import re
import time
from . import service, store, source_registry
from .job_settings import normalize_job_settings
from .youtube import normalize_youtube_url

_RECOVER_ENQUEUE = '''
for _, key in ipairs(KEYS) do
    for _, value in ipairs(redis.call('LRANGE', key, 0, -1)) do
        if value == ARGV[1] then return 0 end
    end
end
redis.call('LPUSH', KEYS[1], ARGV[1])
return 1
'''

def require_active_source(source: dict) -> None:
    if source.get('status') != 'active' or source.get('rights_confirmed') is not True or source.get('platform_permission') is not True or not source.get('authorization_reference'):
        raise PermissionError('Source authorization is pending or disabled')

def recover_import_enqueue(jid: str, queue=None) -> dict:
    """Repair the save/enqueue crash gap atomically against the single-worker lists."""
    from .queueing import PENDING, PROCESSING
    with store.job_lock(jid):
        job=store.load(jid)
        if job['status'] not in {'QUEUED','QUEUE_FAILED'}:
            return job
        if job['status'] == 'QUEUE_FAILED':
            job.update(status='QUEUED',error=None)
            store.save(job)
        try:
            (queue or store.rconn()).eval(_RECOVER_ENQUEUE,2,PENDING,PROCESSING,jid)
        except Exception as exc:
            # A lost Redis reply may follow a successful push. Leave QUEUED so an
            # active worker can proceed; a repeated import safely reconciles it.
            raise RuntimeError('Queue unavailable; job_id=' + jid) from exc
        return store.load(jid)

def fetch_youtube_metadata(url: str) -> dict:
    from yt_dlp import YoutubeDL
    with YoutubeDL({'quiet':True,'no_warnings':True,'noplaylist':True,'skip_download':True,
                   'extract_flat':False,'socket_timeout':20,'retries':2,'js_runtimes':{'deno':{}}}) as ydl:
        return ydl.extract_info(normalize_youtube_url(url), download=False)


def find_existing_youtube(video_id: str) -> dict | None:
    """Read legacy and new identities; callers serialize creation with the ingestion lock."""
    # Explicit editorial revisions share the source; ordinary ingestion prefers the root job.
    for job in sorted(store.all_jobs(),key=lambda j:bool(j.get('source_parent_job'))):
        if job.get('source_type') != 'youtube':
            continue
        stored = job.get('youtube_video_id') or (job.get('youtube_metadata') or {}).get('video_id')
        if not stored:
            try:
                stored = normalize_youtube_url(job.get('source_url') or '').split('v=')[-1]
            except ValueError:
                continue
        if stored == video_id:
            return job
    return None


def public_metadata(url: str) -> dict:
    canonical = normalize_youtube_url(url)
    try:
        metadata = fetch_youtube_metadata(canonical)
    except Exception as exc:
        raise ValueError('Não foi possível consultar o vídeo público. Verifique se está disponível e sem restrição de membros/login.') from exc
    vid = canonical.split('v=')[-1]
    if not isinstance(metadata, dict) or metadata.get('id') != vid:
        raise ValueError('Metadata video identity mismatch')
    channel_id = source_registry.validate_channel_id(metadata.get('channel_id'))
    title, creator = metadata.get('title'), metadata.get('channel') or metadata.get('uploader')
    if any(not isinstance(v, str) or not v.strip() or len(v) > 4000 for v in (title, creator)):
        raise ValueError('YouTube metadata requires title and creator')
    return {'video_id': vid, 'channel_id': channel_id, 'title': title, 'creator': creator,
            'source_url': canonical, 'language': metadata.get('language'), 'duration': metadata.get('duration')}

def verify_source_metadata(metadata: dict, video_id: str, source: dict, settings: dict) -> dict:
    """Fail closed on missing channel/language or ambiguous video kinds under narrower policy."""
    if not isinstance(metadata,dict) or metadata.get('id',metadata.get('video_id')) != video_id:
        raise ValueError('Metadata video identity mismatch')
    if metadata.get('channel_id') != source['channel_id']:
        raise PermissionError('Metadata channel does not match authorized source')
    if source.get('policy_mode') == 'not_enforced':
        if metadata.get('is_live') or metadata.get('live_status') in {'is_live','is_upcoming','post_live'}:
            raise PermissionError('Live or upcoming video is not supported')
        return {'video_id':video_id,'channel_id':source['channel_id'],'title':str(metadata.get('title') or video_id)[:4000],
                'language':metadata.get('language'),'video_kind':'unspecified','model_scope':'external' if settings.get('editorial_planner') == 'hermes_first' else 'local',
                'live_status':metadata.get('live_status'),'duration':metadata.get('duration')}
    require_active_source(source)
    language = metadata.get('language')
    # A primary language grants its regional variants; a regional grant stays narrow.
    valid_language = isinstance(language, str) and re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', language)
    normalized = language.lower() if valid_language else ''
    allowed = [value.lower() for value in source['allowed_languages'] if isinstance(value, str)]
    if not normalized or not any(normalized == value or ('-' not in value and normalized.startswith(value + '-')) for value in allowed):
        raise PermissionError('Metadata language is missing or not authorized')
    live = metadata.get('live_status')
    if metadata.get('is_live') or live in {'is_live','is_upcoming','post_live'}:
        raise PermissionError('Live or upcoming video is not supported')
    kinds = source['allowed_video_kinds']
    # Duration is not proof of Shorts status. Ordinary extractor metadata is ambiguous.
    kind = 'live_archive' if live == 'was_live' or metadata.get('was_live') else None
    if kind is None and metadata.get('is_short') is True:
        kind = 'short'
    elif kind is None and metadata.get('is_short') is False:
        kind = 'video'
    if (kind and kind not in kinds) or (kind is None and not {'video','short'}.issubset(kinds)):
        raise PermissionError('Video kind missing, ambiguous or not authorized')
    hermes_allowed = settings.get('editorial_planner') == 'hermes_first' and 'external' in source['allowed_model_scopes']
    model_scope = 'external' if hermes_allowed or any(settings.get(k) == 'external' for k in ('ranker_mode','director_mode','llm_backend','llm_model')) else 'local'
    if model_scope not in source['allowed_model_scopes']:
        raise PermissionError('Model scope is not authorized')
    return {'video_id':video_id,'channel_id':source['channel_id'],'title':str(metadata.get('title') or video_id)[:4000],
            'language':language,'video_kind':kind or 'video_or_short','model_scope':model_scope,
            'live_status':live,'duration':metadata.get('duration')}

def ingest_youtube(payload: dict, *, queue=None, metadata_fetcher=None, job_details=None, enforce_source_policy=True) -> dict:
    fields = {'source_url','source_id','settings','owner_message','actor_id'}
    if not isinstance(payload,dict) or set(payload)-fields:
        raise ValueError('Unknown ingestion fields')
    if job_details is None:
        job_details={}
    if not isinstance(job_details,dict) or set(job_details)-{'creator','license_note','video_title','qc_settings','assembly_plan'}:
        raise ValueError('Invalid trusted job details')
    if os.getenv('ENABLE_YOUTUBE_DOWNLOAD','true').lower() != 'true':
        raise PermissionError('YouTube ingestion is disabled in this installation')
    url = normalize_youtube_url(payload.get('source_url',''))
    video_id = url.split('v=')[-1]
    settings = normalize_job_settings(payload.get('settings'))
    if settings['ranker_mode'] == 'external':
        raise ValueError('External plans are not supported by URL ingestion; use the explicit external-plan workflow')
    metadata = (metadata_fetcher or fetch_youtube_metadata)(url)
    if not isinstance(metadata,dict):
        raise ValueError('Invalid metadata')
    channel_id = source_registry.validate_channel_id(metadata.get('channel_id'))
    if payload.get('source_id') and payload['source_id'] != channel_id:
        raise PermissionError('Requested source does not match metadata channel')
    # Serialize imports across API/UI processes, and discover already-persisted jobs after crashes.
    with store.file_lock(store.ROOT / 'source-ingestion.lock'):
        with store.file_lock(store.ROOT / 'sources.lock'):
            if enforce_source_policy:
                try:
                    source = source_registry.get_source(channel_id)
                except KeyError as exc:
                    raise PermissionError('Channel is not registered as authorized') from exc
            else:
                try:
                    existing_source = source_registry.get_source(channel_id)
                except KeyError:
                    existing_source = {}
                source = {**existing_source, 'channel_id':channel_id,
                          'name':existing_source.get('name') or metadata.get('channel') or metadata.get('uploader') or channel_id,
                          'policy_mode':'not_enforced', 'allowed_model_scopes':['local','external']}
            verified = verify_source_metadata(metadata,video_id,source,settings)
            verified['source_url'] = url
            existing = find_existing_youtube(video_id)
            if existing:
                if existing.get('status') in {'QUEUED','QUEUE_FAILED'}:
                    existing = recover_import_enqueue(existing['id'],queue=queue)
                return {'job':existing,'duplicate':True}
            context = {key:payload[key] for key in ('owner_message','actor_id') if key in payload}
            if any(not isinstance(v,str) or not v.strip() or len(v)>4000 for v in context.values()):
                raise ValueError('Invalid ingestion context')
            job = service.create_job({'source_url':url,'creator':source['name'],
                'license_note':source.get('authorization_reference') or 'Autorização não verificada',
                'rights_confirmed':source.get('rights_confirmed') is True,
                'platform_permission':source.get('platform_permission') is True,'settings':settings,**job_details},queue=queue,
                source_provenance={'source_id':channel_id,'source_snapshot':source,
                    'youtube_video_id':video_id,'video_title':verified['title'],'original_name':verified['title'],
                    'youtube_metadata':verified,'ingestion_context':context,'metadata_verified_at':time.time()})
            return {'job':job,'duplicate':False}
