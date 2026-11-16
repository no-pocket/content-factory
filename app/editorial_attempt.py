"""Explicit, idempotent editorial attempt linked to an existing YouTube job."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from . import source_ingestion, source_registry, store
from .job_settings import normalize_job_settings


def create_attempt(parent_id, request_id, *, queue=None, metadata_fetcher=None, reserved_actor=None, owner_message=None):
    if str(uuid.UUID(request_id)) != request_id:
        raise ValueError('Canonical request UUID required')
    if reserved_actor is not None and (not isinstance(reserved_actor,str) or not reserved_actor.startswith('telegram:') or not isinstance(owner_message,str) or not owner_message.strip() or len(owner_message)>4000):
        raise ValueError('Reserved attempts require actor and owner instruction')
    with store.job_lock(parent_id):
        parent = store.load(parent_id)
        if parent.get('source_type') != 'youtube' or not parent.get('source_url'):
            raise ValueError('A YouTube source is required')
        if parent.get('status') not in ('FAILED', 'PARTIAL_FAILED', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'EDITORIAL_NO_CANDIDATES'):
            raise ValueError('Original job must be idle')
        child_id = str(uuid.uuid5(uuid.UUID(parent_id), 'editorial-attempt:' + request_id))
        url = source_ingestion.normalize_youtube_url(parent['source_url'])
        video_id = url.split('v=')[-1]
        metadata = (metadata_fetcher or source_ingestion.fetch_youtube_metadata)(url)
        with store.file_lock(store.ROOT / 'sources.lock'):
            source = source_registry.get_source(metadata.get('channel_id'))
            settings = normalize_job_settings({**parent['settings'], 'editorial_planner':'hermes_first',
                                               'editorial_protocol':2, **({'editorial_fallback_local':False} if reserved_actor else {})})
            verified = source_ingestion.verify_source_metadata(metadata, video_id, source, settings)
            if verified['model_scope'] != 'external':
                raise PermissionError('External editorial scope is required')
            source_path = Path(parent.get('source') or '').resolve()
            if not source_path.is_relative_to(store.INPUT.resolve()) or not source_path.is_file():
                raise ValueError('Cached source is unavailable')
            with source_path.open('rb') as handle:
                fingerprint = hashlib.file_digest(handle, 'sha256').hexdigest()
            if not parent.get('source_fingerprint') or parent['source_fingerprint'] != fingerprint:
                raise ValueError('Cached source fingerprint missing or changed')
            transcript_path = store.JOBS / (parent_id + '.transcript.json')
            transcript = transcript_path.read_bytes()
            parsed = json.loads(transcript)
            if not isinstance(parsed, dict) or not isinstance(parsed.get('segments'), list):
                raise ValueError('Cached transcript is invalid')
            target = store.JOBS / (child_id + '.json')
            if target.exists():
                child = store.load(child_id)
                if child.get('source_parent_job') != parent_id or child.get('editorial_attempt_request_id') != request_id:
                    raise ValueError('Attempt identity collision')
                if child.get('editorial_reserved_actor') != reserved_actor or child.get('editorial_attempt_owner_message') != owner_message:
                    raise ValueError('Attempt request reused with different intent')
            else:
                fields = ('schema_version','settings_version','source','source_type','source_url','original_name',
                          'creator','video_title','license_note','platform_permission','qc_settings',
                          'editorial_policy','editorial_versions','outro_snapshot','transcript_model')
                child = {key:copy.deepcopy(parent[key]) for key in fields if key in parent}
                from .provenance import component_snapshot
                child['component_snapshot'] = component_snapshot(settings)
                if isinstance(child.get('editorial_versions'), dict):
                    child['editorial_versions']['component_snapshot_id'] = child['component_snapshot']['snapshot_id']
                verified['source_url'] = url
                child.update(id=child_id, source_parent_job=parent_id, editorial_attempt_request_id=request_id,
                    editorial_attempt_actor=reserved_actor or 'local_operator', editorial_reserved_actor=reserved_actor,
                    editorial_attempt_owner_message=owner_message,
                    source_id=source['channel_id'], source_snapshot=source, youtube_video_id=video_id,
                    youtube_metadata=verified, metadata_verified_at=time.time(), source_fingerprint=fingerprint,
                    settings=settings, editorial_protocol=2, status='QUEUED', candidates=[], approved=[],
                    decision_history=[], error=None, created_at=time.time())
                sidecar = store.JOBS / (child_id + '.transcript.json')
                temp = store.JOBS / (child_id + '.transcript.tmp')
                temp.write_bytes(transcript)
                os.replace(temp, sidecar)
                store.save(child)
    if child['status'] in ('QUEUED', 'QUEUE_FAILED'):
        return source_ingestion.recover_import_enqueue(child_id, queue=queue)
    return child
