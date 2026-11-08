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
