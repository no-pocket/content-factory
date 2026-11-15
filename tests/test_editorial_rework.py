import copy
import json
import pytest
from app import service, store
from test_editorial_service_v2 import v2job, review_request
from test_source_ingestion import Queue


@pytest.fixture
def reviewed_source(v2job, monkeypatch, tmp_path):
    monkeypatch.setenv('CONTENT_FACTORY_AUTO_REWORK', 'true')
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    monkeypatch.setattr(store, 'INPUT', tmp_path/'input'); store.INPUT.mkdir()
    source=store.INPUT/'source.mp4'; source.write_bytes(b'synthetic authorized source')
    job=v2job; job['source']=str(source)
    second=copy.deepcopy(job['candidates'][0])
    for key in ('candidate_id','artifact_id','artifact_manifest','render_history','candidate_version','render_revision'):
        second.pop(key,None)
    second.update(start=20,end=40)
    job['candidates'].append(second)
    from app.artifacts import register_render
    register_render(job,1)
    store.save(job)
    transcript={'language':'pt','segments':[{'start':i,'end':i+1,'text':'palavra',
        'words':[{'start':i,'end':i+.8,'text':'palavra'}]} for i in range(60)]}
    (store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(transcript))
    q=Queue(); monkeypatch.setattr(store,'rconn',lambda:q)
    return job,q


def finish(job):
    first=review_request(job,decision='APPROVED_WITH_ADJUSTMENTS',comment_raw='Gancho bom, corte a introdução longa.')
    service.review_candidate_v2(job['id'],job['candidates'][0]['candidate_id'],first)
    assert len(store.all_jobs())==1  # Wait for every candidate.
    current=store.load(job['id'])
    last=review_request(current,decision='REJECTED',comment_raw='Use só a explicação final, sem a repetição.',
                        expected_artifact_id=job['candidates'][1]['artifact_id'],rejection_domain='UNSPECIFIED')
    result=service.review_candidate_v2(job['id'],job['candidates'][1]['candidate_id'],last)
    return result,last


def test_final_review_creates_one_child_with_all_feedback_and_preserves_original(reviewed_source):
    job,q=reviewed_source; original=copy.deepcopy(job['settings'])
    result,last=finish(job)
    child=store.load(result['rework_job_id'])
    assert child['source_parent_job']==job['id'] and child['status']=='QUEUED'
    assert child['settings']['clip_count']==1 and child['settings']['timeline_v3'] is True
    assert child['candidates']==[] and child['approved']==[]
    assert len(child['editorial_rework']['feedback'])==2
    assert child['editorial_rework']['feedback'][1]['comment']=='Use só a explicação final, sem a repetição.'
    assert (store.JOBS/(child['id']+'.transcript.json')).is_file()
    assert store.load(job['id'])['settings']==original
    assert service.review_candidate_v2(job['id'],job['candidates'][1]['candidate_id'],last)==result
    assert q.ids==[child['id']] and len(store.all_jobs())==2


def test_queue_failure_does_not_lose_committed_reviews_and_recovers_once(reviewed_source):
    from app.editorial_rework import reconcile_requests
    job,q=reviewed_source
    original=q.eval
    q.eval=lambda *args: (_ for _ in ()).throw(OSError('offline'))
    result,_=finish(job)
    assert len(store.load(job['id'])['feedback_events'])==2
    assert store.load(job['id'])['rework_requests'][-1]['state']=='PENDING'
    q.eval=original
    reconcile_requests(queue=q); reconcile_requests(queue=q)
    assert q.ids==[result['rework_job_id']]


def test_revision_keeps_the_frozen_licensed_outro_snapshot(reviewed_source):
    job,q=reviewed_source
    job['settings']['outro_asset_id']='licensed-ending'
    job['outro_snapshot']={'asset_id':'licensed-ending','sha256':'a'*64,'duration':3}
    store.save(job)
    result,_=finish(job)
    assert store.load(result['rework_job_id'])['outro_snapshot']==job['outro_snapshot']


def test_comparative_feedback_and_current_notes_change_the_revision_fingerprint(reviewed_source):
    from app.editorial_rework import register_request
    job,q=reviewed_source; finish(job)
    parent=store.load(job['id']); view=service.get_editorial_view(parent)
    row=view['candidates'][0]
    row['current_event']['relative_assessment']={'comparison_set_id':parent['id'],'preferred_candidate_id':row['candidate_id'],
        'alternatives':[{'candidate_id':row['candidate_id'],'candidate_version':row['candidate_version']}],
        'all_options_below_bar':False,'comment':'Prefiro o início deste.','confirmed_by':'human'}
    parent['editorial_notes']=[{'candidate_id':row['candidate_id'],'artifact_id':row['artifact_id'],'text':'Mantenha a demonstração.'}]
    child_id=register_request(parent,view)
    frozen=parent['rework_requests'][-1]
    assert child_id!=parent['rework_requests'][0]['child_id']
    assert frozen['feedback'][0]['relative_assessment']['comment']=='Prefiro o início deste.'
    assert frozen['feedback'][0]['notes']==['Mantenha a demonstração.']


def test_rework_refuses_arbitrary_source_path_without_losing_review(reviewed_source, tmp_path):
    job,q=reviewed_source; outside=tmp_path/'outside.mp4'; outside.write_bytes(b'private')
    job['source']=str(outside); store.save(job)
    result,_=finish(job)
    parent=store.load(job['id'])
    assert parent['rework_requests'][-1]['state']=='BLOCKED'
    assert not q.ids and not (store.JOBS/(result['rework_job_id']+'.json')).exists()


def test_plan_uses_source_ids_bounds_and_observed_slow_speech():
    from app.editorial_rework import validate_plan
    segments=[{'start':i*3,'end':(i+1)*3,'text':'duas palavras',
               'words':[{'start':i*3,'end':i*3+.5,'text':'duas'},
                        {'start':i*3+1,'end':i*3+2,'text':'palavras'}]} for i in range(15)]
    feedback=[{'candidate_id':'one','start':0,'end':15},{'candidate_id':'two','start':30,'end':45}]
    proposal={'segments':[{'first':0,'last':4,'purpose':'contexto'}, {'first':10,'last':14,'purpose':'conclusão'}],
              'considered':[0,1],'pace':'auto','rationale':'Combinar contexto e conclusão, sem repetir.'}
    plan,pace=validate_plan(proposal,segments,45,feedback,{'min_seconds':8,'max_seconds':60,'auto_pace':True})
    assert len(plan['segments'])==2 and plan['duration']<30 and pace['rate']<=1.15
    with pytest.raises(ValueError):
        validate_plan({**proposal,'considered':[0]},segments,45,feedback,{'min_seconds':8,'max_seconds':60})
    with pytest.raises(ValueError):
        validate_plan({**proposal,'segments':[{'first':0,'last':99,'purpose':'inventado'}]},segments,45,feedback,{'min_seconds':8,'max_seconds':60})


def test_model_receives_every_feedback_and_incomplete_response_never_falls_back(monkeypatch):
    from app.editorial_rework import propose_revision
    from app.job_settings import normalize_job_settings
    segments=[{'start':i*2,'end':(i+1)*2,'text':'fala completa.',
               'words':[{'start':i*2,'end':(i+1)*2,'text':'fala'}]} for i in range(10)]
    job={'settings':normalize_job_settings({'llm_backend':'kepler_gpu','min_seconds':8}),
         'editorial_rework':{'feedback':[{'candidate_id':'first','start':0,'end':20,'comment':'CORRIJA O GANCHO'}]}}
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'done_reason':'length','response':'{}'}).encode()
    def call(request,timeout):
        payload=json.loads(request.data)
        assert 'CORRIJA O GANCHO' in payload['prompt'] and 'fala completa.' in payload['prompt']
        return Reply()
    monkeypatch.setattr('urllib.request.urlopen',call)
    with pytest.raises(ValueError,match='no silent fallback'):
        propose_revision(job,{'segments':segments},20)


def test_revision_plan_ids_are_local_to_the_observed_source_table():
    from app.editorial_rework import validate_plan
    segments=[{'start':i*3,'end':i*3+3,'text':'fala completa',
               'words':[{'start':i*3,'end':i*3+2,'text':'fala'}]} for i in range(100)]
    feedback=[{'candidate_id':'one','start':200,'end':220}]
    proposal={'segments':[{'first':0,'last':9,'purpose':'história observada'}],
              'considered':[0],'pace':'natural','rationale':'IDs locais, não posições globais.'}
    plan,_=validate_plan(proposal,segments,300,feedback,{'min_seconds':8,'max_seconds':60})
    assert plan['segments'][0]['source_in']==186


def test_next_round_context_uses_the_actual_discontinuous_source_intervals():
    from app.editorial_rework import source_table
    segments=[{'start':i*3,'end':i*3+3,'text':'fala'} for i in range(100)]
    feedback=[{'start':0,'end':290,'source_intervals':[[0,10],[270,290]]}]
    table=source_table(segments,feedback)
    assert table and not any(30<=row[1]<=240 for row in table)


def test_model_selects_only_prevalidated_choices_without_repair_loops(monkeypatch):
    from app.editorial_rework import propose_revision
    from app.job_settings import normalize_job_settings
    segments=[{'start':i*2,'end':(i+1)*2,'text':'fala completa.',
               'words':[{'start':i*2,'end':(i+1)*2,'text':'fala'}]} for i in range(10)]
    job={'settings':normalize_job_settings({'llm_backend':'kepler_gpu','min_seconds':8}),
         'editorial_rework':{'feedback':[{'candidate_id':'one','start':0,'end':20,'comment':'Retire repetições.'}]}}
    calls=[]
    class Reply:
        def __init__(self,choice):self.choice=choice
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'done_reason':'stop','response':json.dumps({
            'plan_id':self.choice,'pace':'natural','rationale':'Uma história, sem repetição.'})}).encode()
    def call(request,timeout):
        payload=json.loads(request.data);calls.append(payload)
        assert 0 in payload['format']['properties']['plan_id']['enum']
        return Reply(0)
    monkeypatch.setattr('urllib.request.urlopen',call)
    result=propose_revision(job,{'segments':segments},20)
    assert len(calls)==1 and len(result)==1
    calls.clear()
    monkeypatch.setattr('urllib.request.urlopen',lambda request,timeout:(calls.append(request) or Reply(999)))
    with pytest.raises(ValueError):propose_revision(job,{'segments':segments},20)
    assert len(calls)==1
