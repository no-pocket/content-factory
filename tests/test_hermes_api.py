import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
import pytest
from app import api, store
from test_editorial_service_v2 import v2job, review_request

@pytest.fixture
def hermes_server(monkeypatch):
    monkeypatch.setenv('CONTENT_FACTORY_API_TOKEN','synthetic-general-token-long-enough')
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_TOKEN','synthetic-hermes-token-long-enough')
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_ACTOR_ID','123456')
    server=HTTPServer(('127.0.0.1',0),api.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def call(path,body=None,token='synthetic-hermes-token-long-enough'):
        request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request) as reply:return reply.status,json.load(reply)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
    yield call
    server.shutdown();server.server_close();thread.join()


def test_hermes_token_is_scoped_and_candidate_has_no_paths(v2job,hermes_server):
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}"
    status,payload=hermes_server(route)
    assert status==200
    assert payload['artifact_id']==c['artifact_id']
    assert 'file' not in payload and 'timeline_file' not in payload
    assert str(store.OUTPUT) not in json.dumps(payload)
    assert hermes_server('/v1/jobs')[0]==401
    assert hermes_server(route,token='synthetic-general-token-long-enough')[0]==401


def test_hermes_can_save_caption_as_suggestion_without_approval(v2job, hermes_server):
    import uuid
    job=v2job; clip=job['candidates'][0]
    route=f"/v2/hermes/jobs/{job['id']}/candidates/{clip['candidate_id']}"
    payload={'owner_message':'Crie outra legenda', 'caption':{'request_id':str(uuid.uuid4()),
        'expected_artifact_id':clip['artifact_id'], 'provider':'instagram', 'text':'Uma sugestão para revisão.'}}
    assert hermes_server(route+'/captions', {'caption':payload['caption']})[0]==422
    status,result=hermes_server(route+'/captions',payload)
    assert status==200 and result['text']=='Uma sugestão para revisão.'
    assert hermes_server(route+'/captions',payload)[1]==result
    assert hermes_server(route)[1]['social_captions']['instagram']['origin']=='hermes'
    assert not store.load(job['id']).get('feedback_events')
    assert hermes_server(route+'/captions',{**payload,'caption':{**payload['caption'],'text':'Outra'}})[0]==409


def test_caption_request_id_cannot_be_reused_for_new_artifact(v2job, hermes_server):
    import uuid
    from app.artifacts import register_render
    job=v2job; clip=job['candidates'][0]
    route=f"/v2/hermes/jobs/{job['id']}/candidates/{clip['candidate_id']}/captions"
    payload={'owner_message':'Crie outra legenda', 'caption':{'request_id':str(uuid.uuid4()),
        'expected_artifact_id':clip['artifact_id'], 'provider':'instagram', 'text':'Sugestão.'}}
    assert hermes_server(route,payload)[0]==200
    updated=store.load(job['id'])
    register_render(updated,0)
    store.save(updated)
    payload['caption']['expected_artifact_id']=updated['candidates'][0]['artifact_id']
    assert hermes_server(route,payload)[0]==409


def test_hermes_can_read_scoped_source_transcript(v2job, hermes_server):
    path=store.JOBS / (v2job['id']+'.transcript.json')
    path.write_text(json.dumps({'language':'pt','segments':[{'start':1,'end':2,'text':'Trecho de teste','private':'ignore'}]}),encoding='utf-8')
    status,result=hermes_server('/v2/hermes/jobs/'+v2job['id']+'/transcript')
    assert status==200 and result['segments']==[{'start':1,'end':2,'text':'Trecho de teste'}]


def test_hermes_cannot_read_transcript_for_local_only_source(v2job, hermes_server):
    job=store.load(v2job['id'])
    job['source_snapshot']={'allowed_model_scopes':['local']}
    store.save(job)
    assert hermes_server('/v2/hermes/jobs/'+job['id']+'/transcript')[0]==403
    caption={'request_id':'00000000-0000-4000-8000-000000000001','expected_artifact_id':job['candidates'][0]['artifact_id'],'provider':'instagram','text':'teste'}
    route=f"/v2/hermes/jobs/{job['id']}/candidates/{job['candidates'][0]['candidate_id']}/captions"
    assert hermes_server(route,{'owner_message':'Nova legenda','caption':caption})[0]==403


def test_hermes_review_requires_explicit_owner_message_and_trusted_actor(v2job,hermes_server):
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/reviews"
    review=review_request(j)
    assert hermes_server(route,{'review':review})[0]==422
    assert not store.load(j['id']).get('feedback_events')
    status,payload=hermes_server(route,{'owner_message':'Aprovo este candidato.','review':review})
    assert status==200
    assert payload['event']['actor']=={'kind':'human','id':'telegram:123456','channel':'telegram'}
    assert payload['event']['comment_raw']=='Aprovo este candidato.'
    assert hermes_server(route,{'owner_message':'Aprovo','review':{**review,'request_id':'bad'}})[0]==422


def test_hermes_review_still_rejects_replaced_media(v2job,hermes_server):
    j=v2job;c=j['candidates'][0]
    from pathlib import Path
    Path(c['file']).write_bytes(b'changed media')
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/reviews"
    assert hermes_server(route,{'owner_message':'Aprovo','review':review_request(j)})[0]==409
    assert not store.load(j['id']).get('feedback_events')

def test_hermes_short_credential_never_enables_bridge(v2job,hermes_server,monkeypatch):
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_TOKEN','short')
    j=v2job;c=j['candidates'][0]
    assert hermes_server(f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}",token='short')[0]==401


def test_hermes_group_selection_does_not_create_review(v2job,hermes_server,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    status,listing=hermes_server('/v2/hermes/groups')
    assert status==200 and len(listing['groups'])==1
    gid=listing['groups'][0]['group_id']
    status,group=hermes_server('/v2/hermes/groups/'+gid)
    assert status==200
    import uuid
    identity={k:group['candidates'][0][k] for k in ('job_id','candidate_id','candidate_version','render_revision','artifact_id')}
    body={'owner_message':'Escolho este como final, ainda com ajustes.', 'selection':{'request_id':str(uuid.uuid4()),'expected_revision':group['revision'],'selected':[identity]}}
    status,result=hermes_server('/v2/hermes/groups/'+gid+'/selection',body)
    assert status==200
    assert result['selection']['actor_id']=='telegram:123456'
    assert result['selection']['comment_raw']==body['owner_message']
    assert not store.load(v2job['id']).get('feedback_events')
    assert not result['candidates'][0]['release_ready']

def test_hermes_equal_credentials_fail_closed(v2job,hermes_server,monkeypatch):
    monkeypatch.setenv('CONTENT_FACTORY_API_TOKEN','synthetic-hermes-token-long-enough')
    assert hermes_server('/v1/jobs')[0]==503
    assert hermes_server('/v2/hermes/groups')[0]==503


def test_hermes_note_records_literal_feedback_without_deciding(v2job,hermes_server):
    import uuid
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/notes"
    body={'owner_message':'Gostei mais, mas corte o começo.','note':{'request_id':str(uuid.uuid4()),'expected_artifact_id':c['artifact_id']}}
    status,reply=hermes_server(route,body)
    assert status==200
    saved=store.load(j['id'])
    assert not saved.get('feedback_events')
    assert reply['note']['text']==body['owner_message']
    assert reply['note']['actor']['id']=='telegram:123456'
    assert hermes_server(route,body)[1]==reply
    assert len(store.load(j['id'])['editorial_notes'])==1
    assert hermes_server(route,{**body,'owner_message':'Mudou o pedido'})[0]==409
    from pathlib import Path
    Path(c['file']).write_bytes(b'changed source')
    body['note']['request_id']=str(uuid.uuid4())
    assert hermes_server(route,body)[0]==409

def test_hermes_new_rejection_supersedes_approval_without_inventing_scores(v2job, hermes_server):
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/reviews"
    assert hermes_server(route, {'owner_message':'bom','review':review_request(j)})[0]==200
    rejection=review_request(store.load(j['id']), decision='REJECTED')
    status,reply=hermes_server(route, {'owner_message':'áudio desincronizado, recusado','review':rejection})
    assert status==200
    assert reply['event']['rejection_domain']=='UNSPECIFIED'
    assert reply['event']['decision']=='REJECTED'
    assert len(store.load(j['id'])['feedback_events'])==2

def test_hermes_note_after_review_preserves_new_messages_and_provenance(v2job,hermes_server):
    import uuid
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}"
    assert hermes_server(route+'/reviews', {'owner_message':'bom','review':review_request(j)})[0]==200
    source={'chat_id':'-100123','thread_id':'1687','message_id':1705,'sent_at':'2026-11-08T15:30:05+00:00'}
    body={'owner_message':'novo comentário literal','note':{'request_id':str(uuid.uuid4()),'expected_artifact_id':c['artifact_id'],'source_message':source}}
    status,reply=hermes_server(route+'/notes',body)
    assert status==200
    assert reply['note']['source_message']==source
    assert hermes_server(route+'/notes',body)[1]==reply
    body['note']['request_id']=str(uuid.uuid4());body['note']['source_message']={**source,'message_id':1706}
    assert hermes_server(route+'/notes',body)[0]==200
    saved=store.load(j['id'])
    assert len(saved['editorial_notes'])==2
    assert len(saved['feedback_events'])==1

def test_hermes_note_keeps_delivered_old_artifact_explicit(v2job,hermes_server):
    import uuid
    from app.artifacts import register_render
    j=v2job;c=j['candidates'][0];old=c['artifact_id']
    register_render(j,0);store.save(j)
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}"
    body={'owner_message':'o render anterior está ruim','note':{'request_id':str(uuid.uuid4()),'expected_artifact_id':old}}
    status,reply=hermes_server(route+'/notes',body)
    assert status==200
    assert reply['note']['artifact_id']==old
    assert reply['note']['render_revision']==1
    status,current=hermes_server(route)
    assert current['notes']==[]
    assert current['historical_notes']==[reply['note']]

def test_hermes_delivery_binding_survives_review_and_resolves_message(v2job,hermes_server,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}"
    binding={'artifact_id':c['artifact_id'],'chat_id':'-100123','thread_id':'1687','message_id':1704,
             'master_sha256':c['artifact_manifest']['files']['mp4']['sha256']}
    status,reply=hermes_server(route+'/deliveries',{'delivery':binding})
    assert status==200
    assert hermes_server(route+'/deliveries',{'delivery':binding})[1]==reply
    assert hermes_server('/v2/hermes/deliveries/-100123/1704')[1]['candidate_id']==c['candidate_id']
    assert hermes_server(route)[1]['deliveries']==[reply]

def test_delivery_binding_cannot_be_reassigned(v2job,hermes_server,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/deliveries"
    binding={'artifact_id':c['artifact_id'],'chat_id':'-100124','thread_id':'1687','message_id':1704,
             'master_sha256':c['artifact_manifest']['files']['mp4']['sha256']}
    assert hermes_server(route,{'delivery':{**binding,'master_sha256':'0'*64}})[0]==409
    assert hermes_server(route,{'delivery':binding})[0]==200
    assert hermes_server(route,{'delivery':{**binding,'thread_id':'1688'}})[0]==409

@pytest.mark.parametrize('field,value',[('master_sha256',None),('master_sha256','bad'),('artifact_id',None),('artifact_id','sha256:bad')])
def test_delivery_rejects_malformed_identity(v2job,hermes_server,monkeypatch,tmp_path,field,value):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    j=v2job;c=j['candidates'][0]
    binding={'artifact_id':c['artifact_id'],'master_sha256':c['artifact_manifest']['files']['mp4']['sha256'],
             'chat_id':'-100123','thread_id':'1687','message_id':1704}
    status,_=hermes_server(f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/deliveries",{'delivery':{**binding,field:value}})
    assert status==422


def test_delivery_rejects_missing_master_and_tampered_manifest(v2job,hermes_server,monkeypatch,tmp_path):
    from pathlib import Path
    from app.artifacts import register_render
    monkeypatch.setattr(store,'ROOT',tmp_path)
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/deliveries"
    Path(c['file']).unlink();register_render(j,0);store.save(j)
    binding={'artifact_id':c['artifact_id'],'master_sha256':None,'chat_id':'-100123','thread_id':'1687','message_id':1704}
    assert hermes_server(route,{'delivery':binding})[0] in (409,422)
    c['artifact_manifest']['files']['mp4']={'sha256':'a'*64,'path':'missing.mp4'};store.save(j)
    assert hermes_server(route,{'delivery':{**binding,'master_sha256':'a'*64}})[0]==409

def test_delivery_ack_media_optional_and_unknown_is_explicit(v2job,hermes_server,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    j=v2job;c=j['candidates'][0]
    route=f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/deliveries"
    binding={'artifact_id':c['artifact_id'],'master_sha256':c['artifact_manifest']['files']['mp4']['sha256'],
             'chat_id':'-100125','thread_id':'1687','message_id':1704}
    status,reply=hermes_server(route,{'delivery':binding})
    assert status==200 and reply['sent_media'] is None
    # Receipt geometry is what Telegram acknowledged, even when it was wrong.
    media={'width':1280,'height':720,'duration':43,'supports_streaming':True}
    status,reply=hermes_server(route,{'delivery':{**binding,'message_id':1705,'sent_media':media}})
    assert status==200 and reply['sent_media']==media
    assert hermes_server(route,{'delivery':{**binding,'sent_media':media}})[0]==409


@pytest.mark.parametrize('media',[
    {},{'width':720,'height':1280,'duration':43,'supports_streaming':'true'},
    {'width':True,'height':1280,'duration':43,'supports_streaming':True},
    {'width':720,'height':0,'duration':43,'supports_streaming':True},
    {'width':720,'height':1280,'duration':-1,'supports_streaming':True},
    {'width':720,'height':1280,'duration':float('nan'),'supports_streaming':True},
])
def test_delivery_rejects_invalid_ack_media(v2job,hermes_server,monkeypatch,tmp_path,media):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    j=v2job;c=j['candidates'][0]
    binding={'artifact_id':c['artifact_id'],'master_sha256':c['artifact_manifest']['files']['mp4']['sha256'],
             'chat_id':'-100125','thread_id':'1687','message_id':1704,'sent_media':media}
    status,_=hermes_server(f"/v2/hermes/jobs/{j['id']}/candidates/{c['candidate_id']}/deliveries",{'delivery':binding})
    assert status==422
