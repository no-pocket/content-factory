"""Local authorization registry. Records express owner declarations, not license verification."""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from . import store

CHANNEL_ID = re.compile(r'UC[A-Za-z0-9_-]{22}\Z')

def validate_channel_id(value):
    if not isinstance(value, str) or not CHANNEL_ID.fullmatch(value):
        raise ValueError('channel_id requires canonical UC + 22 characters')
    return value

def _path():
    return store.ROOT / 'sources.json'

def list_sources() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(records, list):
        raise ValueError('Invalid source registry')
    return records

def get_source(channel_id: str) -> dict:
    validate_channel_id(channel_id)
    for record in list_sources():
        if record['channel_id'] == channel_id:
            return record
    raise KeyError('Unknown authorized source')

def upsert_source(payload: dict, *, expected_revision: int | None = None) -> dict:
    fields = {'channel_id','name','status','authorization_reference','rights_confirmed',
              'platform_permission','allowed_languages','allowed_video_kinds','allowed_model_scopes'}
    if not isinstance(payload, dict) or set(payload) - fields:
        raise ValueError('Unknown source fields')
    clean = {'status':'pending','authorization_reference':'','rights_confirmed':False,
             'platform_permission':False,'allowed_languages':[],
             'allowed_video_kinds':['video','short'],'allowed_model_scopes':['local'], **payload}
    validate_channel_id(clean.get('channel_id'))
    for key in ('name','authorization_reference'):
        if not isinstance(clean.get(key), str) or len(clean[key]) > 4000:
            raise ValueError('Invalid ' + key)
        clean[key] = clean[key].strip()
    if not clean['name'] or clean['status'] not in {'pending','active','disabled'}:
        raise ValueError('Invalid source name or status')
    for key in ('rights_confirmed','platform_permission'):
        if type(clean[key]) is not bool:
            raise ValueError(key + ' must be boolean')
    for key, choices in (('allowed_languages',None),('allowed_video_kinds',{'video','short','live_archive'}),
                         ('allowed_model_scopes',{'local','external'})):
        values = clean[key]
        if not isinstance(values,list) or len(values)>100 or any(not isinstance(v,str) for v in values):
            raise ValueError('Invalid ' + key)
        if any((v not in choices if choices else not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*',v)) for v in values):
            raise ValueError('Invalid ' + key)
        clean[key] = sorted(set(values))
    if clean['status'] == 'active' and not (clean['rights_confirmed'] and clean['platform_permission'] and clean['authorization_reference']):
        raise ValueError('Active source requires rights, platform permission and authorization_reference')
    store.ROOT.mkdir(parents=True, exist_ok=True)
    with store.file_lock(store.ROOT / 'sources.lock'):
        records = list_sources()
        old = next((r for r in records if r['channel_id'] == clean['channel_id']),None)
        revision = old['revision'] if old else 0
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision != revision):
            raise ValueError('Stale source revision')
        clean.update(revision=revision+1, updated_at=time.time())
        records = [r for r in records if r['channel_id'] != clean['channel_id']] + [clean]
        temp = store.ROOT / ('sources.' + uuid.uuid4().hex + '.tmp')
        try:
            temp.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(temp,_path())
        finally:
            temp.unlink(missing_ok=True)
    return clean
