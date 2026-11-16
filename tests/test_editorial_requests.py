import pytest
from test_source_ingestion import setup
from test_hermes_api import hermes_server
from test_editorial_service_v2 import v2job
from app.editorial_requests import claim, begin_generation, accept_submission, expire

def request():
    return {'state':'REQUESTED','expires_at':100,'lease_version':0,'generation_started':False}

def test_lease_expiry_before_generation_allows_new_claim():
    row=request(); claim(row,actor='a',token='x',now=10,seconds=10)
    claim(row,actor='b',token='y',now=21,seconds=10)
    assert row['lease_version']==2 and row['lease_actor']=='b'
    with pytest.raises(ValueError): begin_generation(row,actor='a',token='x',version=1,now=22)

def test_started_generation_never_restarts_after_lease_expiry():
    row=request(); claim(row,actor='a',token='x',now=10,seconds=10)
    begin_generation(row,actor='a',token='x',version=1,now=11)
    with pytest.raises(ValueError): claim(row,actor='b',token='y',now=21,seconds=10)
    expire(row,now=21)
    assert row['state']=='EXPIRED' and row['failure_kind']=='generation_result_unknown'

def test_accepted_receipt_replays_without_lease_but_cannot_be_changed():
    row=request();claim(row,actor='a',token='x',now=10,seconds=10);begin_generation(row,actor='a',token='x',version=1,now=11)
    result=accept_submission(row,actor='a',token='x',version=1,now=12,submission_id='one',payload_digest='hash',outcome='no_suitable_candidates')
    assert result['state']=='NO_CANDIDATES'
    assert accept_submission(row,actor='a',token='expired',version=1,now=200,submission_id='one',payload_digest='hash',outcome='no_suitable_candidates')==result
    with pytest.raises(ValueError): accept_submission(row,actor='a',token='x',version=1,now=200,submission_id='one',payload_digest='other',outcome='no_suitable_candidates')
    with pytest.raises(ValueError): accept_submission(row,actor='b',token='x',version=1,now=200,submission_id='one',payload_digest='hash',outcome='no_suitable_candidates')

def test_claim_does_not_persist_lease_token():
    row=request();claim(row,actor='a',token='sensitive-token',now=10,seconds=10)
    assert 'sensitive-token' not in repr(row)
    begin_generation(row,actor='a',token='sensitive-token',version=1,now=11)

def test_persisted_claim_and_generation_are_atomic(setup):
    import uuid
    from app import store
    from app.editorial_requests import claim_job, begin_job_generation
    job=store.new_job(None,'fixture','owner','license')
    job['status']='WAITING_EDITORIAL_PLAN'
    job['editorial_request']={'request_id':str(uuid.uuid4()),'state':'REQUESTED','expires_at':100,'lease_version':0,'generation_started':False}
    store.save(job)
    rid=job['editorial_request']['request_id']
    lease=claim_job(job['id'],rid,actor='test',now=10,seconds=10,authorize=lambda _:None)
    assert store.load(job['id'])['editorial_request']['state']=='CLAIMED'
    begin_job_generation(job['id'],rid,actor='test',token=lease['token'],version=lease['version'],now=11,authorize=lambda _:None)
    assert store.load(job['id'])['editorial_request']['generation_started'] is True
    with pytest.raises(ValueError):
        begin_job_generation(job['id'],rid,actor='test',token=lease['token'],version=lease['version'],now=12,authorize=lambda _:None)


@pytest.mark.parametrize('fallback',[True,False])
def test_technical_failure_is_fenced_idempotent_and_records_reason(setup,fallback):
    import uuid
    from app import store
    from app.editorial_requests import claim_job,begin_job_generation,fail_job_generation
    job=store.new_job(None,'fixture','owner','license');rid=str(uuid.uuid4())
    run=str(uuid.uuid4())
    job.update(status='WAITING_EDITORIAL_PLAN',processing_runs=[{'run_id':run,'state':'RUNNING','started_at':1}],
        editorial_request={'job_id':job['id'],'request_id':rid,'run_id':run,
        'state':'REQUESTED','expires_at':100,'lease_version':0,'generation_started':False,'fallback_allowed':fallback})
    store.save(job)
    lease=claim_job(job['id'],rid,actor='test',now=10,seconds=20,authorize=lambda _:None)
    begin_job_generation(job['id'],rid,actor='test',token=lease['token'],version=lease['version'],now=11,authorize=lambda _:None)
    with pytest.raises(ValueError):
        fail_job_generation(job['id'],rid,actor='test',token='wrong',version=lease['version'],now=12,
                            failure_code='model_timeout',authorize=lambda _:None)
    receipt=fail_job_generation(job['id'],rid,actor='test',token=lease['token'],version=lease['version'],now=12,
                                failure_code='model_timeout',authorize=lambda _:None)
    saved=store.load(job['id'])
    assert receipt['state']=='TECHNICAL_FAILED' and saved['editorial_request']['failure_code']=='model_timeout'
    assert saved['editorial_request'].get('fallback_pending',False) is fallback
    assert saved['status']==('WAITING_EDITORIAL_PLAN' if fallback else 'FAILED')
    assert saved['processing_runs'][-1]['state']==('RUNNING' if fallback else 'FAILED')
    assert fail_job_generation(job['id'],rid,actor='test',token='expired',version=0,now=200,
        failure_code='model_timeout',authorize=lambda _:(_ for _ in ()).throw(PermissionError()))==receipt
    with pytest.raises(ValueError):
        fail_job_generation(job['id'],rid,actor='test',token='expired',version=0,now=200,
                            failure_code='invalid_json',authorize=lambda _:None)


def test_scoped_failure_route_reconciles_one_fallback(setup,hermes_server,monkeypatch):
    import time,uuid
    from app import store,hermes_api
    from app.editorial_requests import expire_job_request
    from test_hermes_reprocess import Queue
    monkeypatch.setattr(hermes_api,'_require_external',lambda _:None)
    monkeypatch.setenv('CONTENT_FACTORY_EDITORIAL_TOKEN','synthetic-editorial-token-long-enough')
    token='synthetic-editorial-token-long-enough';rid=str(uuid.uuid4())
    job=store.new_job(None,'fixture','owner','license')
    job.update(status='WAITING_EDITORIAL_PLAN',source_snapshot={'allowed_model_scopes':['external']},
        editorial_request={'job_id':job['id'],'request_id':rid,'state':'REQUESTED','expires_at':time.time()+900,
                           'lease_version':0,'generation_started':False,'fallback_allowed':True})
    store.save(job);base='/v2/hermes/jobs/'+job['id']
    lease=hermes_server(base+'/editorial-claim',{'request_id':rid},token=token)[1]
    assert hermes_server(base+'/editorial-start',{'request_id':rid,'token':lease['token'],'version':lease['version']},token=token)[0]==200
    body={'request_id':rid,'token':lease['token'],'version':lease['version'],'failure_code':'model_timeout'}
    status,receipt=hermes_server(base+'/editorial-failure',body,token=token)
    assert status==200 and receipt['state']=='TECHNICAL_FAILED'
    assert hermes_server(base+'/editorial-failure',body,token=token)[1]==receipt
    queue=Queue()
    expire_job_request(job['id'],now=time.time(),queue=queue,authorize_local=lambda _:None,authorize_external=lambda _:True)
    saved=store.load(job['id'])
    assert saved['status']=='QUEUED' and saved['editorial_planner_fallback']=='model_timeout' and queue.ids==[job['id']]


def test_revoked_source_failure_report_has_distinct_error_code(setup,hermes_server,monkeypatch):
    import time,uuid
    from app import store,hermes_api
    monkeypatch.setattr(hermes_api,'_require_external',lambda _:None)
    monkeypatch.setenv('CONTENT_FACTORY_EDITORIAL_TOKEN','synthetic-editorial-token-long-enough')
    token='synthetic-editorial-token-long-enough';rid=str(uuid.uuid4())
    job=store.new_job(None,'fixture','owner','license')
    job.update(status='WAITING_EDITORIAL_PLAN',source_snapshot={'allowed_model_scopes':['external']},
        editorial_request={'job_id':job['id'],'request_id':rid,'state':'REQUESTED','expires_at':time.time()+900,
                           'lease_version':0,'generation_started':False,'fallback_allowed':True})
    store.save(job);base='/v2/hermes/jobs/'+job['id']
    lease=hermes_server(base+'/editorial-claim',{'request_id':rid},token=token)[1]
    assert hermes_server(base+'/editorial-start',{'request_id':rid,'token':lease['token'],'version':lease['version']},token=token)[0]==200
    monkeypatch.setattr(hermes_api,'_require_external',lambda _:(_ for _ in ()).throw(PermissionError('revoked')))
    status,response=hermes_server(base+'/editorial-failure',{'request_id':rid,'token':lease['token'],
        'version':lease['version'],'failure_code':'model_timeout'},token=token)
    assert status==403 and response['error']['code']=='editorial_source_denied'


def test_persisted_empty_outcome_and_receipt_replay(setup):
    import uuid
    from app import store
    from app.editorial_plan import transcript_digest
    from app.editorial_requests import claim_job, begin_job_generation, submit_job_plan
    job=store.new_job(None,'fixture','owner','license'); ids=[str(uuid.uuid4()) for _ in range(4)]
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Uma fala.','words':[]}]}
    row={'request_id':ids[0],'editorial_attempt_id':ids[1],'job_id':job['id'],'run_id':ids[2], 'source_fingerprint':'a'*64,'duration_ms':10000,'transcript_digest':transcript_digest(tx),'min_seconds':1,'max_seconds':20,'state':'REQUESTED','expires_at':100,'lease_version':0,'generation_started':False}
    job.update(status='WAITING_EDITORIAL_PLAN',editorial_request=row);store.save(job)
    (store.JOBS / (job['id']+'.transcript.json')).write_text(__import__('json').dumps(tx),encoding='utf8')
    plan={'schema_version':'1.0',**{k:row[k] for k in ('job_id','run_id','request_id','editorial_attempt_id')},'submission_id':ids[3],'source':{'source_fingerprint':'a'*64,'duration_ms':10000},'transcript':{'digest':row['transcript_digest'],'canonicalization':'cf-transcript-v1','language':'pt','timebase':'source_ms'},'planner':{'engine':'hermes','provider':'UNKNOWN','model':'UNKNOWN','prompt_version':'v1','invocation_id':'UNKNOWN'},'outcome':'no_suitable_candidates','reason':'Nada adequado','candidates':[]}
    lease=claim_job(job['id'],ids[0],actor='test',now=10,seconds=10,authorize=lambda _:None)
    begin_job_generation(job['id'],ids[0],actor='test',token=lease['token'],version=lease['version'],now=11,authorize=lambda _:None)
    receipt=submit_job_plan(job['id'],plan,actor='test',token=lease['token'],version=lease['version'],now=12,authorize=lambda _:None)
    assert store.load(job['id'])['status']=='EDITORIAL_NO_CANDIDATES'
    assert receipt['state']=='NO_CANDIDATES'
    assert submit_job_plan(job['id'],plan,actor='test',token='expired',version=0,now=200,authorize=lambda _:(_ for _ in ()).throw(PermissionError()))==receipt
    with pytest.raises(ValueError): submit_job_plan(job['id'],{**plan,'reason':'outro'},actor='test',token='expired',version=0,now=200,authorize=lambda _:None)

def test_wait_request_freezes_source_run_and_transcript():
    import uuid
    from app.editorial_requests import prepare_waiting_request
    from app.editorial_plan import transcript_digest
    jid,run=str(uuid.uuid4()),str(uuid.uuid4())
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala','words':[]}]}
    job={'id':jid,'source_fingerprint':'a'*64,'processing_runs':[{'run_id':run}], 'status':'TRANSCRIBING'}
    settings={'min_seconds':1,'max_seconds':20}
    result=prepare_waiting_request(job,tx,10.,settings,now=1,timeout=60)
    assert job['status']=='WAITING_EDITORIAL_PLAN'
    assert result['run_id']==run and result['job_id']==jid and result['transcript_digest']==transcript_digest(tx)
    assert result['expires_at']==61
    assert prepare_waiting_request(job,tx,10.,settings,now=2,timeout=60)['request_id']==result['request_id']
    with pytest.raises(ValueError): prepare_waiting_request(job,{**tx,'language':'en'},10.,settings,now=2,timeout=60)

def test_editorial_planner_setting_preserves_local_default_and_allows_opt_in():
    from app.job_settings import normalize_job_settings
    assert normalize_job_settings({})['editorial_planner']=='local'
    assert normalize_job_settings({'editorial_planner':'hermes_first','editorial_protocol':2})['editorial_planner']=='hermes_first'
    with pytest.raises(ValueError,match='protocol'):
        normalize_job_settings({'editorial_planner':'hermes_first','editorial_protocol':1})
    with pytest.raises(ValueError): normalize_job_settings({'editorial_planner':'anything'})

def test_worker_waits_for_authorized_hermes_and_falls_back_without_scope():
    import uuid
    from app.editorial_requests import start_editorial_if_eligible
    tx={'language':'pt','segments':[]};settings={'editorial_planner':'hermes_first','min_seconds':1,'max_seconds':20}
    base={'id':str(uuid.uuid4()),'source_fingerprint':'a'*64,'processing_runs':[{'run_id':str(uuid.uuid4())}],'status':'TRANSCRIBING'}
    denied=dict(base)
    assert start_editorial_if_eligible(denied,tx,10.,settings,now=1,authorize=lambda _:False) is False
    assert denied['status']=='TRANSCRIBING' and denied['editorial_planner_fallback']=='source_scope_forbids_external'
    with pytest.raises(PermissionError):
        start_editorial_if_eligible(dict(base),tx,10.,{**settings,'editorial_fallback_local':False},now=1,authorize=lambda _:False)
    allowed=dict(base,source_snapshot={'allowed_model_scopes':['external']})
    assert start_editorial_if_eligible(allowed,tx,10.,settings,now=1,authorize=lambda _:True) is True
    assert allowed['status']=='WAITING_EDITORIAL_PLAN'

def test_editorial_request_can_be_claimed_and_started(setup, hermes_server, monkeypatch):
    import uuid
    from app import store, hermes_api
    monkeypatch.setattr(hermes_api, '_require_external', lambda job: None)
    monkeypatch.setattr(hermes_api, '_external_allowed', lambda job: True)
    job=store.new_job(None,'fixture','owner','license')
    rid=str(uuid.uuid4())
    job.update(source_snapshot={'allowed_model_scopes':['external']},status='WAITING_EDITORIAL_PLAN', editorial_request={'request_id':rid,'job_id':job['id'],'state':'REQUESTED','expires_at':__import__('time').time()+600,'lease_version':0,'generation_started':False})
    store.save(job)
    status, body=hermes_server('/v2/hermes/editorial-requests')
    assert status==200 and any(r['job_id']==job['id'] for r in body['requests'])
    path='/v2/hermes/jobs/'+job['id']+'/editorial-claim'
    status, lease=hermes_server(path,{'request_id':rid})
    assert status==200 and lease['token']
    status,_=hermes_server('/v2/hermes/jobs/'+job['id']+'/editorial-start',{'request_id':rid,'token':lease['token'],'version':lease['version']})
    assert status==200 and store.load(job['id'])['editorial_request']['generation_started'] is True

def test_editorial_list_and_claim_deny_local_only_source(setup,hermes_server):
    import uuid,time
    from app import store
    job=store.new_job(None,'fixture','owner','license');rid=str(uuid.uuid4())
    job.update(source_snapshot={'allowed_model_scopes':['local']},status='WAITING_EDITORIAL_PLAN',editorial_request={'job_id':job['id'],'request_id':rid,'state':'REQUESTED','expires_at':time.time()+600,'lease_version':0})
    store.save(job)
    assert all(r['job_id']!=job['id'] for r in hermes_server('/v2/hermes/editorial-requests')[1]['requests'])
    assert hermes_server('/v2/hermes/jobs/'+job['id']+'/editorial-claim',{'request_id':rid})[0]==403

def test_editorial_api_reads_frozen_transcript_and_accepts_empty_plan(setup,hermes_server,monkeypatch):
    import uuid,time,json
    from app import store,hermes_api
    from app.editorial_requests import prepare_waiting_request
    monkeypatch.setattr(hermes_api,'_require_external',lambda _:None)
    monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:True)
    job=store.new_job(None,'fixture','owner','license'); job.update(source_snapshot={'allowed_model_scopes':['external']}, source_fingerprint='a'*64,processing_runs=[{'run_id':str(uuid.uuid4())}],status='TRANSCRIBING')
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala.','words':[]}]}
    row=prepare_waiting_request(job,tx,10,{'min_seconds':1,'max_seconds':20},now=time.time(),timeout=600)
    store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    base='/v2/hermes/jobs/'+job['id']; status, view=hermes_server(base+'/editorial-request')
    assert status==200 and view['transcript']['segments'][0]['segment_id']=='seg-000000'
    status,lease=hermes_server(base+'/editorial-claim',{'request_id':row['request_id']});assert status==200
    assert hermes_server(base+'/editorial-start',{'request_id':row['request_id'],'token':lease['token'],'version':lease['version']})[0]==200
    plan={'schema_version':'1.0',**{k:row[k] for k in ('job_id','run_id','request_id','editorial_attempt_id')},'submission_id':str(uuid.uuid4()),'source':{'source_fingerprint':row['source_fingerprint'],'duration_ms':row['duration_ms']},'transcript':{'digest':row['transcript_digest'],'canonicalization':'cf-transcript-v1','language':'pt','timebase':'source_ms'},'planner':{'engine':'hermes','provider':'UNKNOWN','model':'UNKNOWN','prompt_version':'v1','invocation_id':'UNKNOWN'},'outcome':'no_suitable_candidates','reason':'Sem cortes','candidates':[]}
    body={'token':lease['token'],'version':lease['version'],'plan':plan}
    status,receipt=hermes_server(base+'/editorial-plan',body)
    assert status==200 and receipt['state']=='NO_CANDIDATES'
    assert store.load(job['id'])['status']=='EDITORIAL_NO_CANDIDATES'
    assert hermes_server(base+'/editorial-plan',body)[1]==receipt

def test_accepted_plan_becomes_source_anchored_candidates():
    from app.editorial_requests import materialize_candidates
    tx={'language':'pt','segments':[{'start':0.,'end':5.,'text':'Inicio.','words':[]},{'start':5.,'end':10.,'text':'Fim.','words':[]}]}
    plan={'candidates':[{'proposal_id':'p1','editorial_title':'Titulo','intent':'Motivo','segments':[{'source_in_ms':0,'source_out_ms':10000,'boundary_status':'requires_audio_review'}],'direction':{'pacing':'natural'},'risks':[]}]}
    clips=materialize_candidates(plan,tx)
    assert len(clips)==1 and clips[0]['start']==0 and clips[0]['end']==10
    assert clips[0]['text']=='Inicio. Fim.'
    assert clips[0]['editorial_plan']['proposal_id']=='p1'
    assert clips[0]['boundary_review_required'] is True

def test_audio_boundary_requires_human_confirmation_for_current_render(v2job):
    from app import service, store
    from test_editorial_service_v2 import review_request
    job=v2job;cid=job['candidates'][0]['candidate_id'];job['candidates'][0]['boundary_review_required']=True;store.save(job)
    with pytest.raises(service.Conflict,match='boundary'):
        service.review_candidate_v2(job['id'],cid,review_request(job))
    confirmation=service.confirm_audio_boundary(job['id'],cid,expected_artifact_id=job['candidates'][0]['artifact_id'],actor_id='owner',boundary='both')
    assert confirmation['boundary']=='both' and confirmation['artifact_id']==job['candidates'][0]['artifact_id']
    assert service.review_candidate_v2(job['id'],cid,review_request(job))['event']['decision']=='APPROVED'

def test_accepted_request_reconciles_once_after_lost_queue_reply(setup):
    from app import store
    from app.editorial_requests import reconcile_accepted_plan
    from test_hermes_reprocess import Queue
    job=store.new_job(None,'fixture','owner','license')
    job.update(status='WAITING_EDITORIAL_PLAN',editorial_request={'job_id':job['id'],'state':'ACCEPTED','resume_pending':True})
    store.save(job);q=Queue()
    reconcile_accepted_plan(job['id'],queue=q)
    reconcile_accepted_plan(job['id'],queue=q)
    assert store.load(job['id'])['status']=='QUEUED'
    assert q.ids==[job['id']]

def test_resume_checks_frozen_source_transcript_and_run(tmp_path):
    import hashlib
    from app.editorial_requests import resume_accepted_plan
    from app.editorial_plan import transcript_digest
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala.','words':[]}]}
    plan={'outcome':'candidates_proposed','candidates':[{'proposal_id':'p','editorial_title':'Titulo','intent':'Motivo','segments':[{'source_in_ms':0,'source_out_ms':10000,'boundary_status':'requires_audio_review'}],'direction':{'pacing':'natural'},'risks':[]}]}
    job={'id':'job','source_fingerprint':hashlib.sha256(b'fixture').hexdigest(),'processing_runs':[{'run_id':'run'}], 'editorial_request':{'state':'ACCEPTED','resume_pending':True,'run_id':'run','source_fingerprint':hashlib.sha256(b'fixture').hexdigest(),'transcript_digest':transcript_digest(tx),'plan':plan}}
    assert resume_accepted_plan(job,tx,source)[0]['proposal_source']=='hermes'
    source.write_bytes(b'changed')
    with pytest.raises(ValueError): resume_accepted_plan(job,tx,source)

def test_worker_resumes_accepted_plan_without_new_run_or_model(setup,monkeypatch,tmp_path):
    import hashlib,json,uuid
    from app import store,worker,hermes_api
    from app.editorial_plan import transcript_digest
    from app.source_registry import get_source
    from test_source_ingestion import CHANNEL
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    job=store.new_job(source,'fixture','owner','license',settings={'editorial_protocol':2,'editorial_planner':'hermes_first','duration_mode':'flexible'})
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala.','words':[]}]}
    run=str(uuid.uuid4());plan={'outcome':'candidates_proposed','candidates':[{'proposal_id':'p','editorial_title':'Titulo','intent':'Motivo','segments':[{'source_in_ms':0,'source_out_ms':10000,'boundary_status':'requires_audio_review'}],'direction':{'pacing':'natural'},'risks':[]}]}
    snapshot={**get_source(CHANNEL),'allowed_model_scopes':['local','external']}
    job.update(status='QUEUED',source_snapshot=snapshot,source_fingerprint=hashlib.sha256(b'fixture').hexdigest(),processing_runs=[{'run_id':run,'state':'RUNNING','started_at':1}],editorial_request={'state':'ACCEPTED','resume_pending':True,'run_id':run,'source_fingerprint':hashlib.sha256(b'fixture').hexdigest(),'transcript_digest':transcript_digest(tx),'plan':plan})
    store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    monkeypatch.setattr(worker,'JOBS',store.JOBS);monkeypatch.setattr(worker,'get_duration',lambda _:10.)
    monkeypatch.setattr(worker,'expects_audio',lambda _:True);monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:True)
    def fail(*args,**kwargs): raise AssertionError('local ranker invoked')
    monkeypatch.setattr(worker,'select_highlights',fail)
    def fake_render(job,*args,**kwargs): job['status']='NEEDS_REVIEW';store.save(job)
    monkeypatch.setattr(worker,'render_candidates',fake_render)
    worker.process(job['id']);saved=store.load(job['id'])
    assert saved['status']=='NEEDS_REVIEW' and len(saved['processing_runs'])==1
    assert saved['candidates'][0]['proposal_source']=='hermes'

def test_resume_waits_until_worker_acknowledges_previous_wait(setup):
    from app import store
    from app.editorial_requests import reconcile_accepted_plan
    from test_hermes_reprocess import Queue
    job=store.new_job(None,'fixture','owner','license');job.update(status='WAITING_EDITORIAL_PLAN',editorial_request={'job_id':job['id'],'state':'ACCEPTED','resume_pending':True});store.save(job)
    q=Queue();q.processing=[job['id']]
    reconcile_accepted_plan(job['id'],queue=q)
    assert store.load(job['id'])['status']=='WAITING_EDITORIAL_PLAN' and q.ids==[]
    q.processing=[];reconcile_accepted_plan(job['id'],queue=q)
    assert store.load(job['id'])['status']=='QUEUED' and q.ids==[job['id']]

def test_hermes_direction_uses_declared_natural_preset_without_local_model():
    from app.editorial_requests import hermes_direction
    clip={'editorial_plan':{'editorial_title':'Fala relevante','direction':{'layout_preset_id':'legacy','subtitle_preset_id':'bold_karaoke_v1','pacing':'natural','word_highlight':'only_if_word_timing_reliable'}}}
    hints=hermes_direction(clip)
    assert hints['hook']=='Fala relevante' and hints['pace']=='natural'
    assert hints['effects']==[] and hints['broll']==[]
    clip['editorial_plan']['direction']['layout_preset_id']='unsupported'
    with pytest.raises(ValueError): hermes_direction(clip)

def test_hermes_candidate_does_not_call_local_director():
    from app.candidates import candidate_direction
    clip={'proposal_source':'hermes','editorial_plan':{'editorial_title':'Fala relevante','direction':{'layout_preset_id':'legacy','subtitle_preset_id':'bold_karaoke_v1','pacing':'natural','word_highlight':'only_if_word_timing_reliable'}}}
    def forbidden(*args,**kwargs): raise AssertionError('local director called')
    hints,engine=candidate_direction(clip,{},mode='ollama',model='qwen2.5:3b',llm_backend='ollama',auto_pace=True,local_director=forbidden)
    assert engine=='hermes' and hints['pace']=='natural'


def test_hermes_caption_without_reliable_word_alignment_uses_segment_timing():
    from app.candidates import annotate_caption_qc
    from app.timeline import build_timeline
    clip={'start':0.,'end':8.,'text':'Frase de teste.', 'proposal_source':'hermes'}
    segments=[{'start':0.,'end':7.,'text':'Frase de teste.','words':[]}]
    timeline=build_timeline(clip,segments)
    assert timeline['caption_style']=='phrase_v1'
    assert timeline['layers']['captions']==[{'start':0.,'end':7.,'text':'Frase de teste.'}]
    assert timeline['word_timing_diagnostics']['reason']=='word_alignment_not_verified'
    clipped=build_timeline({**clip,'start':1.},segments)
    assert clipped['layers']['captions']==[]
    assert clipped['word_timing_diagnostics']['partial_segments_omitted']==1
    qc=annotate_caption_qc({'state':'VALID'},{**clip,'timeline':clipped})
    assert qc['state']=='WARNING' and qc['caption_warning']=='caption_coverage_incomplete'
    assert annotate_caption_qc({'state':'FAILED'},{**clip,'timeline':clipped})['state']=='FAILED'


def test_hermes_editorial_title_is_not_dropped_by_subjective_heuristic():
    from app.timeline import build_timeline
    title='Ainda não há preço confirmado para o Brasil'
    clip={'start':0.,'end':8.,'text':'O preço oficial não foi confirmado.', 'title':title, 'proposal_source':'hermes'}
    timeline=build_timeline(clip,[{'start':0.,'end':8.,'text':clip['text'],'words':[]}],edit={'hook':title})
    assert timeline['layers']['text'][0]['text']==title


def test_legacy_approval_also_requires_boundary_confirmation(setup):
    from app import service, store
    job=store.new_job(None,'synthetic','owner','grant')
    job.update(status='NEEDS_REVIEW',candidates=[{'state':'VALID','boundary_review_required':True}])
    store.save(job)
    with pytest.raises(service.Conflict, match='borda'):
        service.review_candidate(job['id'],0,'APPROVED','teste',expected_revision=0)
    with pytest.raises(service.Conflict, match='borda'):
        service.review_job(job['id'],[{'candidate':0,'decision':'APPROVED','reason':'teste','adjustments':'','rework':False}],expected_revision=0)

def test_expired_editorial_request_schedules_only_one_local_fallback(setup):
    import uuid
    from app import store
    from app.editorial_requests import expire_job_request
    from test_hermes_reprocess import Queue
    job=store.new_job(None,'fixture','owner','license');rid=str(uuid.uuid4())
    job.update(status='WAITING_EDITORIAL_PLAN',editorial_request={'job_id':job['id'],'request_id':rid,'state':'REQUESTED','expires_at':10,'lease_version':0,'generation_started':False,'fallback_allowed':True})
    store.save(job);q=Queue()
    expire_job_request(job['id'],now=11,queue=q,authorize_local=lambda _:None)
    saved=store.load(job['id']); assert saved['status']=='QUEUED' and saved['editorial_request']['state']=='EXPIRED'
    assert saved['editorial_request']['fallback_pending'] is True and q.ids==[job['id']]
    expire_job_request(job['id'],now=12,queue=q,authorize_local=lambda _:None)
    assert q.ids==[job['id']]


def test_revoked_external_scope_never_automatically_falls_back(setup):
    from app import store
    from app.editorial_requests import expire_job_request
    from test_hermes_reprocess import Queue
    job=store.new_job(None,'fixture','owner','license')
    job.update(status='WAITING_EDITORIAL_PLAN',editorial_request={'state':'REQUESTED','expires_at':10,'fallback_allowed':True})
    store.save(job); q=Queue()
    expire_job_request(job['id'],now=11,queue=q,authorize_local=lambda _:None,authorize_external=lambda _:False)
    saved=store.load(job['id'])
    assert saved['status']=='FAILED' and saved['editorial_request']['state']=='REVOKED' and q.ids==[]

def test_no_candidates_never_triggers_expiration_fallback(setup):
    from app import store
    from app.editorial_requests import expire_job_request
    from test_hermes_reprocess import Queue
    job=store.new_job(None,'fixture','owner','license');job.update(status='EDITORIAL_NO_CANDIDATES',editorial_request={'state':'NO_CANDIDATES','fallback_allowed':True});store.save(job)
    q=Queue();expire_job_request(job['id'],now=999,queue=q,authorize_local=lambda _:None)
    assert store.load(job['id'])['status']=='EDITORIAL_NO_CANDIDATES' and q.ids==[]


def test_fallback_checks_local_scope_on_both_source_revisions(setup):
    from app import source_registry, store
    from app.editorial_requests import reconcile_editorial_requests
    from test_source_ingestion import CHANNEL, Queue
    snapshot = source_registry.get_source(CHANNEL)
    job = store.new_job(None, 'fixture', 'owner', 'license')
    job.update(status='WAITING_EDITORIAL_PLAN', source_snapshot={**snapshot, 'allowed_model_scopes': ['external']},
               editorial_request={'job_id': job['id'], 'state': 'EXPIRED', 'fallback_allowed': True,
                                  'fallback_pending': True, 'failure_kind': 'request_expired'})
    store.save(job)
    queue = Queue()
    reconcile_editorial_requests(queue=queue)
    assert store.load(job['id'])['editorial_request']['state'] == 'REVOKED'
    assert queue.ids == []


def test_immediate_local_fallback_checks_current_scope(setup, monkeypatch):
    from app import source_registry
    from app.editorial_requests import authorize_local_source
    from test_source_ingestion import CHANNEL
    snapshot=source_registry.get_source(CHANNEL)
    monkeypatch.setattr(source_registry,'get_source',lambda _: {**snapshot,'allowed_model_scopes':['external']})
    with pytest.raises(PermissionError,match='Local model scope'):
        authorize_local_source({'source_snapshot':snapshot})

@pytest.mark.parametrize('failure_state',['EXPIRED','TECHNICAL_FAILED'])
@pytest.mark.parametrize('revocation',['none','external','disabled'])
def test_worker_resumes_expired_request_with_local_fallback(setup,monkeypatch,tmp_path,failure_state,revocation):
    import hashlib,json,uuid
    from app import store,worker,hermes_api,source_registry
    from app.editorial_plan import transcript_digest
    from app.source_registry import get_source
    from test_source_ingestion import CHANNEL
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    job=store.new_job(source,'fixture','owner','license',settings={'editorial_protocol':2,'editorial_planner':'hermes_first','duration_mode':'flexible'})
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala.','words':[]}]}; run=str(uuid.uuid4())
    snapshot={**get_source(CHANNEL),'allowed_model_scopes':['local','external']}
    job.update(status='QUEUED',run_started_at=1,source_snapshot=snapshot,source_fingerprint=hashlib.sha256(b'fixture').hexdigest(),processing_runs=[{'run_id':run,'state':'RUNNING','started_at':1}],editorial_request={'state':failure_state,'fallback_pending':True,'run_id':run,'source_fingerprint':hashlib.sha256(b'fixture').hexdigest(),'transcript_digest':transcript_digest(tx),'failure_kind':'request_expired'})
    store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    monkeypatch.setattr(worker,'JOBS',store.JOBS);monkeypatch.setattr(worker,'get_duration',lambda _:10.);monkeypatch.setattr(worker,'expects_audio',lambda _:True)
    monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:revocation!='external')
    if revocation=='disabled':
        current=get_source(CHANNEL)
        monkeypatch.setattr(source_registry,'get_source',lambda _: {**current,'status':'disabled'})
    calls=[]
    monkeypatch.setattr(worker,'select_highlights',lambda *a,**kw:(calls.append('local') or [{'start':0.,'end':10.,'text':'Fala.','score':1,'reason':'teste'}]))
    def fake_render(job,*args,**kwargs):job['status']='NEEDS_REVIEW';store.save(job)
    monkeypatch.setattr(worker,'render_candidates',fake_render)
    worker.process(job['id']);saved=store.load(job['id'])
    if revocation!='none':
        assert calls==[] and saved['status']=='FAILED' and saved['editorial_request']['state']=='REVOKED'
        return
    assert calls==['local'] and saved['status']=='NEEDS_REVIEW' and len(saved['processing_runs'])==1
    assert saved['editorial_planner_fallback']=='request_expired'


@pytest.mark.parametrize('failure', ['revoked', 'changed_source'])
def test_cached_hermes_candidate_revalidates_rights_and_source(setup,monkeypatch,tmp_path,failure):
    import hashlib,json,uuid
    from app import store,worker,hermes_api
    from app.editorial_plan import transcript_digest
    from test_source_ingestion import CHANNEL
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala.','words':[]}]};run=str(uuid.uuid4())
    job=store.new_job(source,'fixture','owner','license',settings={'editorial_protocol':2,'editorial_planner':'hermes_first'})
    from app.source_registry import get_source
    job.update(status='QUEUED',source_snapshot={**get_source(CHANNEL),'allowed_model_scopes':['local','external']},source_fingerprint=hashlib.sha256(b'fixture').hexdigest(),
        processing_runs=[{'run_id':run,'state':'RUNNING','started_at':1}],run_started_at=1,
        editorial_request={'state':'ACCEPTED','resume_pending':True,'run_id':run,'source_fingerprint':hashlib.sha256(b'fixture').hexdigest(),'transcript_digest':transcript_digest(tx)},
        candidates=[{'start':0.,'end':10.,'text':'Fala.','proposal_source':'hermes'}])
    store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    monkeypatch.setattr(worker,'JOBS',store.JOBS);monkeypatch.setattr(worker,'get_duration',lambda _:10.)
    monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:failure!='revoked')
    if failure=='changed_source': source.write_bytes(b'changed')
    monkeypatch.setattr(worker,'render_candidates',lambda *a,**kw:pytest.fail('must not render after revocation'))
    worker.process(job['id'])
    saved=store.load(job['id'])
    assert saved['status']=='FAILED'
    if failure=='revoked': assert saved['editorial_request']['state']=='REVOKED'


def test_interrupted_editorial_run_is_recorded_when_resumed(setup,monkeypatch,tmp_path):
    import hashlib,json,uuid
    from app import store,worker,hermes_api
    from app.editorial_plan import transcript_digest
    from app.source_registry import get_source
    from test_source_ingestion import CHANNEL
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala.','words':[]}]};run=str(uuid.uuid4())
    job=store.new_job(source,'fixture','owner','license',settings={'editorial_protocol':2,'editorial_planner':'hermes_first'})
    job.update(status='QUEUED',source_snapshot={**get_source(CHANNEL),'allowed_model_scopes':['local','external']},source_fingerprint=hashlib.sha256(b'fixture').hexdigest(),
        processing_runs=[{'run_id':run,'state':'INTERRUPTED','started_at':1}],run_started_at=1,
        editorial_request={'state':'ACCEPTED','resume_pending':True,'run_id':run,'source_fingerprint':hashlib.sha256(b'fixture').hexdigest(),'transcript_digest':transcript_digest(tx)},
        candidates=[{'start':0.,'end':10.,'text':'Fala.','proposal_source':'hermes'}])
    store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    monkeypatch.setattr(worker,'JOBS',store.JOBS);monkeypatch.setattr(worker,'get_duration',lambda _:10.)
    monkeypatch.setattr(worker,'expects_audio',lambda _:True);monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:True)
    def render(current,*args,**kwargs):
        assert current['processing_runs'][-1]['state']=='RUNNING'
        current['status']='NEEDS_REVIEW';store.save(current)
    monkeypatch.setattr(worker,'render_candidates',render)
    worker.process(job['id'])
    saved=store.load(job['id'])
    assert saved['status']=='NEEDS_REVIEW' and saved['processing_runs'][-1]['resume_events'][0]['previous_state']=='INTERRUPTED'

def test_invalid_submitted_plan_records_objective_error_and_fallback(setup):
    import uuid,json
    from app import store
    from app.editorial_plan import transcript_digest
    from app.editorial_requests import claim_job,begin_job_generation,submit_job_plan
    job=store.new_job(None,'fixture','owner','license');rid=str(uuid.uuid4())
    tx={'language':'pt','segments':[]};row={'job_id':job['id'],'request_id':rid,'state':'REQUESTED','expires_at':100,'lease_version':0,'generation_started':False,'fallback_allowed':True,'transcript_digest':transcript_digest(tx)}
    job.update(status='WAITING_EDITORIAL_PLAN',editorial_request=row);store.save(job)
    (store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    lease=claim_job(job['id'],rid,actor='a',now=10,seconds=10,authorize=lambda _:None)
    begin_job_generation(job['id'],rid,actor='a',token=lease['token'],version=lease['version'],now=11,authorize=lambda _:None)
    plan={'request_id':rid,'submission_id':str(uuid.uuid4())}
    receipt=submit_job_plan(job['id'],plan,actor='a',token=lease['token'],version=lease['version'],now=12,authorize=lambda _:None)
    assert receipt['state']=='INVALID'
    saved=store.load(job['id'])['editorial_request']
    assert saved['state']=='INVALID' and saved['failure_kind']=='invalid_plan' and saved['fallback_pending'] is True
    assert saved['failure_code']=='invalid_plan_schema'
    assert submit_job_plan(job['id'],plan,actor='a',token='expired',version=0,now=999,authorize=lambda _:(_ for _ in ()).throw(PermissionError()))==receipt
    with pytest.raises(ValueError): submit_job_plan(job['id'],{**plan,'extra':'different'},actor='a',token='expired',version=0,now=999,authorize=lambda _:None)

def test_stale_run_submission_does_not_force_fallback(setup):
    import uuid,json
    from app import store
    from app.editorial_plan import transcript_digest
    from app.editorial_requests import claim_job,begin_job_generation,submit_job_plan
    job=store.new_job(None,'fixture','owner','license');rid=str(uuid.uuid4());run=str(uuid.uuid4())
    tx={'language':'pt','segments':[]};row={'job_id':job['id'],'request_id':rid,'run_id':run,'state':'REQUESTED','expires_at':100,'lease_version':0,'generation_started':False,'fallback_allowed':True,'transcript_digest':transcript_digest(tx)}
    job.update(status='WAITING_EDITORIAL_PLAN',editorial_request=row);store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    lease=claim_job(job['id'],rid,actor='a',now=10,seconds=10,authorize=lambda _:None)
    begin_job_generation(job['id'],rid,actor='a',token=lease['token'],version=lease['version'],now=11,authorize=lambda _:None)
    with pytest.raises(ValueError): submit_job_plan(job['id'],{'request_id':rid,'run_id':str(uuid.uuid4()),'submission_id':str(uuid.uuid4())},actor='a',token=lease['token'],version=lease['version'],now=12,authorize=lambda _:None)
    assert store.load(job['id'])['editorial_request']['state']=='CLAIMED'

def test_full_editorial_handoff_with_http_and_isolated_worker(setup,hermes_server,monkeypatch,tmp_path):
    import hashlib,json,time,uuid,importlib.util
    from pathlib import Path
    from app import store,worker,hermes_api
    from app.editorial_requests import prepare_waiting_request,reconcile_accepted_plan
    from test_hermes_reprocess import Queue
    script=Path(__file__).resolve().parents[1]/'integrations/hermes/nopocket-content/skills/content-editorial/scripts/editorial_runner.py'
    spec=importlib.util.spec_from_file_location('runner_integration',script);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    monkeypatch.setattr(hermes_api,'_require_external',lambda _:None);monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:True)
    monkeypatch.setattr('app.source_ingestion.require_active_source',lambda _:None);monkeypatch.setattr('app.source_registry.get_source',lambda _: {'status':'active'})
    source=tmp_path/'synthetic.mp4';source.write_bytes(b'synthetic')
    job=store.new_job(source,'fixture','owner','license',settings={'editorial_protocol':2,'editorial_planner':'hermes_first','duration_mode':'flexible'})
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'Fala de teste.','words':[]}]}
    job.update(status='TRANSCRIBING',source_snapshot={'channel_id':'source','allowed_model_scopes':['external']},source_fingerprint=hashlib.sha256(b'synthetic').hexdigest(),processing_runs=[{'run_id':str(uuid.uuid4()),'state':'RUNNING','started_at':time.time()}])
    row=prepare_waiting_request(job,tx,10,job['settings'],now=time.time(),timeout=600);store.save(job)
    (store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    def api(method,path,body=None):
        status,result=hermes_server('/v2/hermes'+path,body if method=='POST' else None)
        assert status==200,(status,result)
        return result
    proposal={'proposal_id':str(uuid.uuid4()),'editorial_title':'Fala de teste','intent':'Contexto','segments':[{'source_in_ms':0,'source_out_ms':10000,'start_anchor':{'segment_id':'seg-000000','quote':'Fala de teste.'},'end_anchor':{'segment_id':'seg-000000','quote':'Fala de teste.'},'boundary_status':'requires_audio_review'}],'direction':{'layout_preset_id':'legacy','subtitle_preset_id':'bold_karaoke_v1','pacing':'natural','word_highlight':'only_if_word_timing_reliable'},'risks':[]}
    pending=runner.PendingSubmission(tmp_path/'pending.json')
    result=runner.process_request(job['id'],row['request_id'],api=api,invoke=lambda _:{'proposal':{'outcome':'candidates_proposed','candidates':[proposal]},'provider':'UNKNOWN','model':'test','invocation_id':'test'},load_pending=pending.load,save_pending=pending.save,clear_pending=pending.clear)
    assert result['state']=='ACCEPTED'
    q=Queue();reconcile_accepted_plan(job['id'],queue=q);assert q.ids==[job['id']]
    monkeypatch.setattr(worker,'JOBS',store.JOBS);monkeypatch.setattr(worker,'get_duration',lambda _:10.);monkeypatch.setattr(worker,'expects_audio',lambda _:True)
    def fake_render(job,*args,**kwargs): job['status']='NEEDS_REVIEW';store.save(job)
    monkeypatch.setattr(worker,'render_candidates',fake_render)
    worker.process(job['id']);saved=store.load(job['id'])
    assert saved['status']=='NEEDS_REVIEW' and saved['candidates'][0]['proposal_source']=='hermes'
    assert len(saved['processing_runs'])==1

def test_hermes_direction_renders_synthetic_master_and_preview(tmp_path):
    import json,subprocess,uuid
    from app.editorial_requests import materialize_candidates
    from app.candidates import candidate_direction
    from app.timeline import build_timeline
    from app.edit_render import render_edited
    source=tmp_path/'source.mp4'; target=tmp_path/'master.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=256x144:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-c:a','aac',str(source)],check=True)
    tx={'language':'pt','segments':[{'start':0.,'end':3.8,'text':'Teste sintetico.','words':[{'start':0.2,'end':1.,'text':'Teste'},{'start':1.1,'end':2.,'text':'sintetico.'}]}]}
    proposal={'proposal_id':str(uuid.uuid4()),'editorial_title':'Teste sintetico','intent':'Teste','segments':[{'source_in_ms':0,'source_out_ms':3800,'boundary_status':'requires_audio_review'}],'direction':{'layout_preset_id':'legacy','subtitle_preset_id':'bold_karaoke_v1','pacing':'natural','word_highlight':'only_if_word_timing_reliable'},'risks':[]}
    clip=materialize_candidates({'outcome':'candidates_proposed','candidates':[proposal]},tx)[0]
    hints,engine=candidate_direction(clip,{},mode='ollama',model='qwen2.5:3b',llm_backend='ollama',auto_pace=False)
    timeline=build_timeline(clip,tx['segments'],edit=hints)
    result=render_edited(source,'synthetic-'+uuid.uuid4().hex,1,clip,tx['segments'],timeline,{},target,engine='remotion',quality='high')
    assert engine=='hermes' and result=='remotion'
    for path in (target,target.with_suffix('.preview.webm')):
        assert path.stat().st_size>1000
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-f','null','-'],check=True)
    assert json.loads(target.with_suffix('.timeline.json').read_text())['layers']['captions']
