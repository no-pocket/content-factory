"""Cross-job source comparison and independent, artifact-bound final selections.

Public API: list_groups() -> list[dict], get_group(group_id: str) -> dict,
select_finals(group_id: str, request: dict) -> dict. expected_revision is the opaque
revision returned by get_group. selected contains exact five-field identities.
Selection never grants editorial approval or bypasses destination preflight.
"""
from __future__ import annotations
import copy
import json
import os
import uuid
from contextlib import ExitStack
from datetime import datetime, timezone
from . import store
from .artifacts import artifact_manifest, digest
from .editorial_dataset import source_families
from .service import Conflict, get_editorial_view

IDENTITY = ('job_id', 'candidate_id', 'candidate_version', 'render_revision', 'artifact_id')
IDLE = {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'}


def _read():
    path = store.ROOT / 'source-review.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'nodes': {}, 'aliases': {}, 'selections': {}}


def _write(state):
    path = store.ROOT / 'source-review.json'
    temp = path.with_name('source-review.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _groups(state, jobs):
    reconciliations = state.setdefault('reconciliations', {})
    families = source_families(jobs)
    components = {}
    for node, family in families.items():
        components.setdefault(family, []).append(node)
    grouped = {}
    for nodes in components.values():
        previous = sorted({state['nodes'][n] for n in nodes if n in state['nodes']})
        gid = previous[0] if previous else 'source:' + digest({'anchor': sorted(nodes)[0]})
        selected_groups = [old for old in previous if state['selections'].get(old)]
        needs_reconciliation = len(selected_groups)>1 or any(reconciliations.get(old,False) for old in previous)
        for old in previous:
            if old != gid:
                state['aliases'][old] = gid
                # Preserve prior selection history when two confirmed families merge.
                history = state['selections'].pop(old, [])
                state['selections'].setdefault(gid, []).extend(history)
                reconciliations.pop(old,None)
        if needs_reconciliation:
            reconciliations[gid] = True
        if len(previous)>1 and state['selections'].get(gid):
            state['selections'][gid].sort(key=lambda e:(e['created_at'],e['request_id']))
        for node in nodes:
            state['nodes'][node] = gid
        grouped[gid] = [j for j in jobs if j['id'] in nodes]
    return grouped


def _canonical(state, gid):
    while gid in state['aliases']:
        gid = state['aliases'][gid]
    return gid


def _models(job, clip=None):
    comparison = job.get('comparison') or {}
    settings = job.get('settings') or {}
    configured = settings.get('llm_model')
    if configured == 'external':
        configured = None
    return {'label': comparison.get('label') or configured or job.get('ranker_used') or 'Modelo não registrado',
            'engine': comparison.get('engine') or job.get('ranker_used') or settings.get('llm_backend'),
            'backend': settings.get('llm_backend'),
            'ranker_used': job.get('ranker_used'),
            'director_used': (clip or {}).get('director_used') or job.get('director_used'),
            'whisper_model': settings.get('whisper_model') or job.get('model')}


def _job_summary(job):
    return {**{k:copy.deepcopy(job.get(k)) for k in ('id','original_name','status','source_fingerprint','editorial_revision')},
            'model':_models(job)}


def _project(gid, jobs, state, *, fresh=False):
    candidates = []
    manifests = []
    history = state['selections'].get(gid, [])
    reconciliation_required = state.get('reconciliations',{}).get(gid,False)
    selection = history[-1] if history and not reconciliation_required else None
    for job in jobs:
        for index, row in enumerate(get_editorial_view(job)['candidates']):
            clip = job['candidates'][index]
            manifest = artifact_manifest(job, index, presentation_cache=not fresh)
            intact = bool(clip.get('artifact_id') and clip['artifact_id'] == 'sha256:' + digest(manifest)
                          and all(manifest['files'].get(k) for k in ('mp4','webm')))
            manifests.append(manifest)
            row.update(job_id=job['id'], start=clip.get('start'), end=clip.get('end'),
                       model=_models(job,clip), text=clip.get('text', ''), artifact_intact=intact)
            row['selectable'] = intact and job.get('status') in IDLE
            row['selected_current'] = bool(row['selectable'] and selection and any(all(s.get(k) == row.get(k) for k in IDENTITY) for s in selection['selected']))
            row['release_ready'] = bool(row['selectable'] and row.get('normalized_decision') == 'APPROVED'
                and row['technical_state'] in ('VALID','WARNING')
                and not any(e.get('status') == 'OPEN' and e.get('severity') in ('MAJOR','CRITICAL') for e in row['edit_requests']))
            row['overlaps'] = []
            candidates.append(row)
    for row in candidates:
        for other in candidates:
            if row is other:continue
            if all(isinstance(v, (int,float)) for v in (row['start'],row['end'],other['start'],other['end'])):
                seconds = max(0, min(row['end'],other['end'])-max(row['start'],other['start']))
                if seconds:row['overlaps'].append({'job_id':other['job_id'],'candidate_id':other['candidate_id'],'seconds':seconds})
    revision = digest({'jobs':jobs, 'manifests':manifests, 'history':history,'reconciliation_required':reconciliation_required})
    summaries = [_job_summary(j) for j in jobs]
    return {'group_id':gid,'revision':revision,'jobs':summaries,'candidates':candidates,
            'selection':copy.deepcopy(selection),'selection_history':copy.deepcopy(history),
            'reconciliation_required':reconciliation_required}


def list_groups() -> list[dict]:
    with store.file_lock(store.ROOT / '.source-review.lock'):
        state = _read();groups = _groups(state, store.all_jobs());_write(state)
        return [{'group_id':gid,'jobs':[_job_summary(j) for j in jobs],
                 'candidate_count':sum(len(j.get('candidates',[])) for j in jobs)} for gid,jobs in sorted(groups.items())]


def get_group(group_id: str) -> dict:
    with store.file_lock(store.ROOT / '.source-review.lock'):
        state = _read();groups = _groups(state, store.all_jobs());gid = _canonical(state,group_id)
        if gid not in groups:raise ValueError('Unknown source group')
        _write(state)
        return _project(gid,groups[gid],state)


def select_finals(group_id: str, request: dict) -> dict:
    required = {'request_id','expected_revision','selected'}
    if not isinstance(request,dict) or required-set(request) or set(request)-required-{'actor_id','channel','comment_raw'}:
        raise ValueError('Invalid final-selection request fields')
    try:
        if str(uuid.UUID(request['request_id'])) != request['request_id']:raise ValueError('Invalid request ID')
    except (TypeError,AttributeError):raise ValueError('Invalid request ID') from None
    if not isinstance(request['expected_revision'],str) or not isinstance(request['selected'],list):raise ValueError('Invalid selection')
    if any(not isinstance(s,dict) or set(s)!=set(IDENTITY) for s in request['selected']):raise ValueError('Exact artifact identities required')
    for identity in request['selected']:
        if any(not isinstance(identity[k],str) or not identity[k] for k in ('job_id','candidate_id','artifact_id')):
            raise ValueError('Invalid artifact identity')
        if any(type(identity[k]) is not int or identity[k]<1 for k in ('candidate_version','render_revision')):
            raise ValueError('Invalid artifact revision')
    if len({digest(s) for s in request['selected']}) != len(request['selected']):raise ValueError('Duplicate selected candidate')
    for field in ('actor_id','channel','comment_raw'):
        if field in request and (not isinstance(request[field],str) or len(request[field])>8000):raise ValueError('Invalid selection metadata')
    with store.file_lock(store.ROOT / '.source-review.lock'):
        state = _read();groups = _groups(state,store.all_jobs());gid = _canonical(state,group_id)
        if gid not in groups:raise ValueError('Unknown source group')
        with ExitStack() as stack:
            for job in sorted(groups[gid],key=lambda j:j['id']):stack.enter_context(store.job_lock(job['id']))
            # Reload after acquiring every relevant job lock, matching review/retry serialization.
            jobs = [store.load(j['id']) for j in groups[gid]]
            latest_groups = _groups(state,store.all_jobs())
            if gid not in latest_groups or {j['id'] for j in latest_groups[gid]} != {j['id'] for j in jobs}:
                raise Conflict('Source membership changed; refresh comparison')
            history = state['selections'].setdefault(gid,[])
            receipt = next((e for e in history if e['request_id']==request['request_id']),None)
            if receipt:
                if receipt['request_sha256']!=digest(request):raise Conflict('Request ID already used')
                return _project(gid,jobs,state,fresh=True)
            current = _project(gid,jobs,state,fresh=True)
            if current['revision']!=request['expected_revision']:raise Conflict('Source group changed; refresh comparison')
            for identity in request['selected']:
                row = next((r for r in current['candidates'] if all(r.get(k)==identity[k] for k in IDENTITY)),None)
                if not row or not row['selectable']:raise Conflict('Selected artifact is stale, processing or unavailable')
            history.append({'request_id':request['request_id'],'request_sha256':digest(request),
                'created_at':datetime.now(timezone.utc).isoformat(),'actor_id':request.get('actor_id','local-owner'),
                'channel':request.get('channel','streamlit'),'comment_raw':request.get('comment_raw',''),
                'selected':copy.deepcopy(request['selected']),'revision':len(history)+1})
            state['reconciliations'][gid] = False
            _write(state)
            return _project(gid,jobs,state,fresh=True)
