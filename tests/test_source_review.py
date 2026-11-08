import uuid
import pytest
from app import store
from app.artifacts import register_render
from app.source_review import list_groups, get_group, select_finals
from app.service import Conflict

@pytest.fixture
def jobs(tmp_path, monkeypatch):
    for key, sub in [('ROOT',''),('JOBS','work'),('OUTPUT','output')]:
        path=tmp_path/sub;path.mkdir(exist_ok=True);monkeypatch.setattr(store,key,path)
    def add(jid, fingerprint='a'*64, parent=None):
        jid=str(uuid.uuid5(uuid.NAMESPACE_DNS,jid))
        if parent:parent=str(uuid.uuid5(uuid.NAMESPACE_DNS,parent))
        job={'id':jid,'source_fingerprint':fingerprint,'editorial_protocol':2,'status':'NEEDS_REVIEW','candidates':[], 'settings':{'qwen_model':jid},'created_at':1}
        if parent:job['source_parent_job']=parent
        path=store.OUTPUT/jid/'master.mp4';path.parent.mkdir();path.write_bytes(b'master')
        path.with_suffix('.preview.webm').write_bytes(b'preview')
        job['candidates']=[{'start':0,'end':10,'file':str(path),'state':'VALID'}]
        register_render(job,0);store.save(job);return job
    return add

def request(group, selected=None):
    return {'request_id':str(uuid.uuid4()),'expected_revision':group['revision'],'selected':selected if selected is not None else [{k:group['candidates'][0][k] for k in ('job_id','candidate_id','candidate_version','render_revision','artifact_id')}]}

def test_stable_group_same_source_and_pending_jobs(jobs):
    jobs('b'); group=list_groups()[0];jobs('a');jobs('c',fingerprint=None,parent='b')
    current=get_group(group['group_id'])
    assert current['group_id']==group['group_id']
    assert len(current['jobs'])==3 and len(current['candidates'])==3
    jobs('unrelated',fingerprint='b'*64)
    assert len(list_groups())==2

def test_zero_many_and_idempotency_are_separate_from_approval(jobs):
    jobs('a');jobs('b');group=get_group(list_groups()[0]['group_id'])
    selected=[{k:r[k] for k in ('job_id','candidate_id','candidate_version','render_revision','artifact_id')} for r in group['candidates']]
    req=request(group,selected);saved=select_finals(group['group_id'],req)
    assert len(saved['selection']['selected'])==2
    assert all(not store.load(str(uuid.uuid5(uuid.NAMESPACE_DNS,j))).get('approved') for j in ('a','b'))
    assert select_finals(group['group_id'],req)['selection']==saved['selection']
    with pytest.raises(Conflict):select_finals(group['group_id'],request(group,[]))
    empty=select_finals(group['group_id'],request(saved,[]))
    assert empty['selection']['selected']==[]

def test_replaced_artifact_and_stale_request(jobs):
    job=jobs('a');group=get_group(list_groups()[0]['group_id']);req=request(group)
    select_finals(group['group_id'],req)
    from pathlib import Path
    Path(job['candidates'][0]['file']).write_bytes(b'replaced')
    current=get_group(group['group_id'])
    assert current['candidates'][0]['selected_current'] is False
    with pytest.raises(Conflict):select_finals(group['group_id'],request(current))


def test_new_jobs_invalidate_open_comparison_and_request_reuse_conflicts(jobs):
    jobs('a');group=get_group(list_groups()[0]['group_id']);req=request(group,[])
    jobs('b')
    with pytest.raises(Conflict):select_finals(group['group_id'],req)
    current=get_group(group['group_id']);req=request(current,[])
    select_finals(group['group_id'],req)
    changed=dict(req,comment_raw='different')
    with pytest.raises(Conflict):select_finals(group['group_id'],changed)

def test_parent_without_fingerprint_and_model_metadata(jobs):
    parent=jobs('root',fingerprint=None)
    group=list_groups()[0]
    child=jobs('child',fingerprint=None,parent='root')
    current=get_group(group['group_id'])
    assert {j['id'] for j in current['jobs']}=={parent['id'],child['id']}
    assert all(r['model'] and r['overlaps'] for r in current['candidates'])

def test_selection_does_not_make_pending_candidate_ready(jobs):
    jobs('a');group=get_group(list_groups()[0]['group_id'])
    selected=select_finals(group['group_id'],request(group))
    assert selected['candidates'][0]['selected_current']
    assert not selected['candidates'][0]['release_ready']
    assert selected['candidates'][0]['normalized_decision']=='PENDING'


def test_concurrent_selection_only_one_writer_wins(jobs):
    from concurrent.futures import ThreadPoolExecutor
    jobs('a');group=get_group(list_groups()[0]['group_id'])
    requests=[request(group,[]) for _ in range(2)]
    def submit(req):
        try:return select_finals(group['group_id'],req)
        except Conflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(submit,requests))
    assert sum(result is not None for result in results)==1

def test_processing_job_cannot_be_selected_and_identity_types_are_strict(jobs):
    job=jobs('a');job['status']='RENDERING';store.save(job)
    group=get_group(list_groups()[0]['group_id'])
    assert not group['candidates'][0]['selectable']
    with pytest.raises(Conflict):select_finals(group['group_id'],request(group))
    job['status']='NEEDS_REVIEW';store.save(job)
    group=get_group(group['group_id']);req=request(group)
    req['selected'][0]['render_revision']=True
    with pytest.raises(ValueError):select_finals(group['group_id'],req)

def test_normal_models_are_distinct_from_shared_backend(jobs):
    a=jobs('a');b=jobs('b')
    for job,model in ((a,'qwen2.5:3b'),(b,'qwen2.5:1.5b')):
        job['ranker_used']='ollama';job['settings']={'llm_model':model,'llm_backend':'ollama'};store.save(job)
    group=get_group(list_groups()[0]['group_id'])
    assert {j['model']['label'] for j in group['jobs']}=={'qwen2.5:3b','qwen2.5:1.5b'}
    assert all(j['model']['engine']=='ollama' for j in group['jobs'])


def test_merging_selected_groups_requires_explicit_reconciliation(jobs):
    a=jobs('a');b=jobs('b',fingerprint='b'*64)
    groups=list_groups();old_ids=[g['group_id'] for g in groups]
    for gid in old_ids:
        group=get_group(gid);select_finals(gid,request(group))
    b['source_parent_job']=a['id'];store.save(b)
    merged=get_group(old_ids[0])
    assert merged['reconciliation_required']
    assert merged['selection'] is None
    assert len(merged['selection_history'])==2
    assert not any(r['selected_current'] for r in merged['candidates'])
    assert get_group(old_ids[1])['group_id']==merged['group_id']
    selected=[{k:r[k] for k in ('job_id','candidate_id','candidate_version','render_revision','artifact_id')} for r in merged['candidates']]
    resolved=select_finals(merged['group_id'],request(merged,selected))
    assert not resolved['reconciliation_required']
    assert len(resolved['selection_history'])==3
    assert all(r['selected_current'] for r in resolved['candidates'])
    assert not get_group(old_ids[1])['reconciliation_required']

def test_requested_model_and_actual_fallback_are_both_visible(jobs):
    job=jobs('a');job['settings']={'llm_model':'qwen2.5:3b','llm_backend':'ollama'}
    job['ranker_used']='heuristic_fallback';job['candidates'][0]['director_used']='heuristic_fallback'
    store.save(job)
    group=get_group(list_groups()[0]['group_id'])
    model=group['candidates'][0]['model']
    assert model['label']=='qwen2.5:3b'
    assert model['backend']=='ollama'
    assert model['engine']=='heuristic_fallback'
    assert model['ranker_used']=='heuristic_fallback'
    assert model['director_used']=='heuristic_fallback'
    from app.source_review_ui import _model_label
    assert 'heuristic_fallback' in _model_label(model)
    assert 'qwen2.5:3b' in _model_label(model)
