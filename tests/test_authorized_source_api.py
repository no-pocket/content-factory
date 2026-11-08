import sys
from types import SimpleNamespace
from test_hermes_api import hermes_server
from test_editorial_service_v2 import v2job


def test_source_registry_scopes_and_admin_mutation(hermes_server, monkeypatch):
    calls = []
    record = {'channel_id': 'UC' + 'a' * 22, 'name': 'Authorized', 'status': 'pending', 'revision': 1}
    monkeypatch.setitem(sys.modules, 'app.source_registry', SimpleNamespace(
        list_sources=lambda: [record], get_source=lambda channel_id: record,
        upsert_source=lambda source, expected_revision=None: calls.append((source, expected_revision)) or record))
    assert hermes_server('/v2/hermes/sources') == (200, {'sources': [{**record, 'authorization_confirmed': False}]})
    assert hermes_server('/v2/hermes/sources/' + record['channel_id'])[0] == 200
    body = {'source': record, 'expected_revision': 0}
    assert hermes_server('/v2/sources', body)[0] == 401
    assert hermes_server('/v2/hermes/sources', body)[0] == 404
    assert calls == []
    assert hermes_server('/v2/sources', body, token='synthetic-general-token-long-enough')[0] == 200
    assert calls == [(record, 0)]


def test_hermes_ingest_explicit_instruction_actor_and_duplicate(hermes_server, monkeypatch):
    calls = []
    job = {'id': 'job', 'status': 'QUEUED', 'source': '/private/input', 'candidates': [{'text': 'PRIVATE TRANSCRIPT'}]}
    def ingest(payload):
        calls.append(payload)
        return {'job': job, 'duplicate': len(calls) > 1}
    monkeypatch.setitem(sys.modules, 'app.source_ingestion', SimpleNamespace(ingest_youtube=ingest))
    action = {'source_url': 'https://youtu.be/abcdefghijk'}
    assert hermes_server('/v2/hermes/ingest', {'ingest': action})[0] == 422
    body = {'owner_message': 'Importe este vídeo autorizado.', 'ingest': action}
    assert hermes_server('/v2/hermes/ingest', {**body, 'ingest': {**action, 'actor_id': 'owner'}})[0] == 422
    assert hermes_server('/v2/hermes/ingest', {**body, 'ingest': {**action, 'model_scope': 'local'}})[0] == 422
    assert calls == []
    status, reply = hermes_server('/v2/hermes/ingest', body)
    assert status == 201 and reply['duplicate'] is False and 'source' not in reply['job']
    assert calls[0]['settings']['editorial_protocol'] == 2
    assert calls[0]['settings']['duration_mode'] == 'flexible'
    assert [calls[0]['settings'][key] for key in ('min_seconds', 'target_seconds', 'max_seconds')] == [8, 40, 180]
    assert hermes_server('/v2/hermes/ingest', {**body, 'ingest': {**action, 'settings': {'editorial_protocol': 1}}})[0] == 422
    assert calls[0]['actor_id'] == 'telegram:123456'
    assert calls[0]['owner_message'] == body['owner_message']
    status, duplicate = hermes_server('/v2/hermes/ingest', body)
    assert status == 200
    assert 'PRIVATE TRANSCRIPT' not in str(duplicate)

def test_local_only_job_cannot_escape_through_hermes(v2job, hermes_server, monkeypatch, tmp_path):
    from app import store
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    job = v2job
    job['source_snapshot'] = {'allowed_model_scopes': ['local']}
    store.save(job)
    from app.source_review import list_groups
    gid = list_groups()[0]['group_id']
    assert hermes_server('/v2/hermes/groups')[1] == {'groups': []}
    assert hermes_server('/v2/hermes/groups/' + gid)[0] == 403
    base = f"/v2/hermes/jobs/{job['id']}/candidates/{job['candidates'][0]['candidate_id']}"
    for suffix in ('', '/media?artifact_id=' + job['candidates'][0]['artifact_id']):
        assert hermes_server(base + suffix)[0] == 403
    assert hermes_server(base + '/notes', {'owner_message': 'note', 'note': {}})[0] == 403
    assert hermes_server('/v2/hermes/jobs/' + job['id'])[1] == {
        key: job.get(key) for key in ('id', 'status', 'created_at', 'updated_at')}

def test_current_source_revocation_blocks_old_external_snapshot(v2job, hermes_server, monkeypatch, tmp_path):
    from app import store
    from app.source_registry import upsert_source
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    source = upsert_source({'channel_id': 'UC' + 'c' * 22, 'name': 'Owner', 'allowed_model_scopes': ['local']})
    job = v2job
    job['source_snapshot'] = {**source, 'allowed_model_scopes': ['local', 'external']}
    job['source_id'] = source['channel_id']
    store.save(job)
    assert hermes_server(f"/v2/hermes/jobs/{job['id']}/candidates/{job['candidates'][0]['candidate_id']}")[0] == 403

from test_source_ingestion import setup, metadata, Queue


def test_hermes_ingest_persists_defaults_and_explicit_classic(setup, hermes_server, monkeypatch):
    from app import store, source_ingestion
    queue = Queue()
    monkeypatch.setattr(store, 'rconn', lambda: queue)
    monkeypatch.setattr(source_ingestion, 'fetch_youtube_metadata', metadata)
    body = {'owner_message': 'Importe esta URL.', 'ingest': setup}
    status, receipt = hermes_server('/v2/hermes/ingest', body)
    assert status == 201
    saved = store.load(receipt['job']['id'])
    assert saved['editorial_protocol'] == 2
    assert saved['settings']['duration_mode'] == 'flexible'
    assert [saved['settings'][key] for key in ('min_seconds', 'target_seconds', 'max_seconds')] == [8, 40, 180]
    assert saved['ingestion_context']['actor_id'] == 'telegram:123456'
    assert queue.ids == [saved['id']]
    # An explicit classic request keeps its own normalized limits.
    from app import hermes_api
    calls = []
    monkeypatch.setattr(source_ingestion, 'ingest_youtube', lambda request: calls.append(request) or {'job': saved, 'duplicate': True})
    body['ingest'] = {**setup, 'settings': {'duration_mode': 'classic'}}
    assert hermes_server('/v2/hermes/ingest', body)[0] == 200
    from app.job_settings import normalize_job_settings
    settings = normalize_job_settings(calls[0]['settings'])
    assert settings['duration_mode'] == 'classic' and settings['max_seconds'] == 60

def test_hermes_source_projection_redacts_owner_evidence(hermes_server, monkeypatch, tmp_path):
    from app import store
    from app.source_registry import upsert_source
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    record = upsert_source({'channel_id': 'UC' + 'd' * 22, 'name': 'Canal', 'authorization_reference': 'PRIVATE AGREEMENT'})
    for path in ('/v2/hermes/sources', '/v2/hermes/sources/' + record['channel_id']):
        status, payload = hermes_server(path)
        assert status == 200
        assert 'PRIVATE AGREEMENT' not in str(payload)
        assert 'authorization_reference' not in str(payload)
    assert hermes_server('/v2/sources', token='synthetic-general-token-long-enough')[1]['sources'][0]['authorization_reference'] == 'PRIVATE AGREEMENT'
