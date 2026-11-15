"""Web adapter regressions; private data and real publishers are never used."""
import copy
import importlib.util
import io
import uuid

import pytest


def test_web_adapter_exists():
    assert importlib.util.find_spec('app.web_api') is not None, 'FastAPI web adapter is required'


@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import web_api, store, service, asset_library, publication_schedule, publishing, source_ingestion
    monkeypatch.setattr(source_ingestion, 'fetch_youtube_metadata', lambda url: {
        'id':url.split('v=')[-1], 'title':'Título de teste', 'channel':'Canal de teste',
        'channel_id':'UC'+'a'*22, 'language':'pt', 'live_status':'not_live', 'duration':120})
    monkeypatch.setenv('CONTENT_FACTORY_WEB_TOKEN', 'test-web-token-' + 'a' * 32)
    monkeypatch.setenv('CONTENT_FACTORY_WEB_HOSTS', 'testserver,localhost:8501')
    for key, name in [('ROOT', ''), ('JOBS', 'work'), ('INPUT', 'input'), ('OUTPUT', 'output')]:
        folder = tmp_path / name
        folder.mkdir(exist_ok=True)
        monkeypatch.setattr(store, key, folder)
    monkeypatch.setattr(asset_library, 'ROOT', tmp_path)
    monkeypatch.setattr(publication_schedule, 'ROOT', tmp_path / 'publication_schedule')
    monkeypatch.setattr(publishing, 'ROOT', tmp_path / 'publishing')
    monkeypatch.setattr(store, 'rconn', lambda: type('Queue', (), {
        'lpush': lambda *a: None, 'llen': lambda *a: 0, 'get': lambda *a: None, 'eval': lambda *a: 0})())
    monkeypatch.setattr(service, 'verify_reviewable', lambda *a: True)
    with TestClient(web_api.app, headers={'X-Content-Factory-Web-Token': 'test-web-token-' + 'a' * 32}) as client:
        yield client


def make_job(protocol=2):
    from app import store
    from app.artifacts import register_render
    job = store.new_job(None, 'synthetic.mp4', 'test', 'synthetic permission',
                        settings={'editorial_protocol': protocol})
    folder = store.OUTPUT / job['id']
    folder.mkdir(parents=True)
    master = folder / 'candidate_1.mp4'
    master.write_bytes(b'0123456789')
    master.with_suffix('.preview.webm').write_bytes(b'preview-bytes')
    master.with_suffix('.timeline.json').write_text('{}')
    job.update(status='NEEDS_REVIEW', candidates=[{'start': 0, 'end': 20, 'text': 'Synthetic speech.',
               'state': 'VALID', 'file': str(master), 'timeline_file': str(master.with_suffix('.timeline.json'))}])
    register_render(job, 0)
    store.save(job)
    return job


def request_review(client, job, *, payload=None, seen=None, request_id=None):
    row = client.get('/api/jobs/' + job['id']).json()['cands'][0]
    body = {'seen': seen or {'artifact': row['artifact'], 'n': len(row['hist']), 'revision': row['revision']},
            'p': payload or {'dec': 'APPROVED', 'comment': '', 'reasons': [], 'adjust': '', 'rating': {}, 'grade': None},
            'request_id': request_id or str(uuid.uuid4())}
    return client.post(f"/api/jobs/{job['id']}/candidates/{row['id']}/review", json=body), body


def test_auth_origin_and_host(web):
    assert web.get('/api/settings', headers={'X-Content-Factory-Web-Token': ''}).status_code == 401
    assert web.get('/api/settings', headers={'Host': 'evil.test'}).status_code == 403
    assert web.post('/api/jobs', json={}, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert web.get('/api/settings', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert web.get('/api/settings').json()['youtube_enabled'] is True


def test_youtube_lookup_keeps_title_and_rights_separate_and_deduplicates_video_id(web, monkeypatch):
    from app import source_ingestion, store
    monkeypatch.setattr(source_ingestion, 'fetch_youtube_metadata', lambda url: {
        'id':'dQw4w9WgXcQ','title':'Título real','channel':'Criador real','channel_id':'UC'+'a'*22,
        'language':'pt','live_status':'not_live','duration':120})
    info = web.post('/api/youtube/metadata',json={'source_url':'https://youtu.be/dQw4w9WgXcQ'}).json()
    assert info['title'] == 'Título real' and info['creator'] == 'Criador real'
    assert 'license_note' not in info
    payload = {'source_url':'https://youtu.be/dQw4w9WgXcQ','creator':info['creator'],'video_title':info['title'],
               'license_note':'Referência de autorização','rights_confirmed':True,'platform_permission':True}
    first = web.post('/api/jobs',json=payload)
    second = web.post('/api/jobs',json={**payload,'source_url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared'})
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()['id'] == second.json()['id']
    assert len(store.all_jobs()) == 1
    saved = store.load(first.json()['id'])
    assert saved['youtube_video_id'] == 'dQw4w9WgXcQ'
    assert saved['video_title'] == 'Título real'
    assert saved['license_note'] == 'Referência de autorização'


def test_upload_rights_snapshot_and_no_paths(web, monkeypatch):
    from app import store
    data = {'creator': 'test', 'license_note': 'grant', 'rights_confirmed': False,
            'settings': {'editorial_protocol': 2, 'whisper_model': 'tiny', 'render_fallback_ffmpeg': False}}
    import json
    assert web.post('/api/jobs', data={'metadata': json.dumps(data)},
                    files={'file': ('a.mp4', b'media')}).status_code == 403
    data['rights_confirmed'] = True
    response = web.post('/api/jobs', data={'metadata': json.dumps(data)}, files={'file': ('a.mp4', b'media')})
    assert response.status_code == 201, response.text
    job = response.json()
    before = copy.deepcopy(store.load(job['id'])['settings'])
    monkeypatch.setenv('WHISPER_MODEL', 'large-v3')
    assert store.load(job['id'])['settings'] == before
    assert before['render_fallback_ffmpeg'] is False
    assert before['whisper_model'] == 'tiny'
    assert 'source' not in job and str(store.ROOT) not in response.text


def test_youtube_requires_platform_and_honors_false(web, monkeypatch):
    data = {'source_url': 'https://youtu.be/dQw4w9WgXcQ', 'creator': 'test', 'license_note': 'grant',
            'rights_confirmed': True, 'platform_permission': False}
    assert web.post('/api/jobs', json=data).status_code == 403
    data['platform_permission'] = True
    monkeypatch.setenv('ENABLE_YOUTUBE_DOWNLOAD', 'false')
    assert web.post('/api/jobs', json=data).status_code == 403
    monkeypatch.setenv('ENABLE_YOUTUBE_DOWNLOAD', 'true')
    assert web.post('/api/jobs', json=data).status_code == 201


def test_review_history_and_artifact_conflicts_are_atomic(web):
    from app import store
    job = make_job()
    response, body = request_review(web, job)
    assert response.status_code == 200, response.text
    cid = job['candidates'][0]['candidate_id']
    route = f"/api/jobs/{job['id']}/candidates/{cid}/review"
    assert web.post(route, json=body).status_code == 200  # Same request: idempotent receipt.
    assert web.post(route, json={**body, 'request_id': str(uuid.uuid4())}).status_code == 409
    loaded = store.load(job['id'])
    assert len(loaded['feedback_events']) == 1
    from pathlib import Path
    Path(loaded['candidates'][0]['file']).write_bytes(b'changed')
    response, _ = request_review(web, job)
    assert response.status_code == 409
    assert len(store.load(job['id'])['feedback_events']) == 1


def test_candidate_history_is_checked_independently_from_global_revision(web):
    from app import store
    job = make_job()
    row = web.get('/api/jobs/' + job['id']).json()['cands'][0]
    response, _ = request_review(web, job, seen={'artifact': row['artifact'], 'n': 1, 'revision': 0})
    assert response.status_code == 409
    assert store.load(job['id']).get('feedback_events', []) == []


def test_failed_candidate_rejection_and_legacy_limits(web):
    from app import store
    job = make_job()
    job['candidates'][0]['state'] = 'FAILED'
    store.save(job)
    payload = {'dec': 'REJECTED', 'comment': 'Technical failure', 'reasons': ['TECHNICAL_FAILURE'],
               'adjust': '', 'rating': {}, 'grade': 0}
    response, _ = request_review(web, job, payload=payload)
    assert response.status_code == 200, response.text
    assert response.json()['cands'][0]['grade'] == 0
    legacy = make_job(1)
    response, _ = request_review(web, legacy, payload={**payload, 'dec': 'ADJ'})
    assert response.status_code == 422


def test_source_revision_conflict_and_no_job_created(web):
    from app import store
    source = {'id': 'UC' + 'a' * 22, 'name': 'test', 'status': 'pending', 'ref': '', 'rights': False,
              'platform': False, 'langs': 'pt', 'kinds': ['video'], 'scopes': ['local'], 'rev': 0}
    route = '/api/sources/' + source['id']
    assert web.put(route, json={'r': source, 'expectedRev': 0}).status_code == 200
    assert web.put(route, json={'r': source, 'expectedRev': 0}).status_code == 409
    assert store.all_jobs() == []


def test_media_range_head_paths_and_sanitization(web):
    from app import store
    job = make_job()
    cid = job['candidates'][0]['candidate_id']
    route = f"/api/jobs/{job['id']}/candidates/{cid}/media/mp4"
    response = web.get(route, headers={'Range': 'bytes=2-5'})
    assert response.status_code == 206 and response.content == b'2345'
    assert web.head(route).headers['content-length'] == '10'
    assert web.get(route + '?artifact=old').status_code == 409
    assert web.get(route.replace('/mp4', '/passwd')).status_code == 422
    assert web.get('/api/jobs/invalid').status_code == 422
    job['error'] = 'secret redis://localhost:6379 ' + str(store.ROOT)
    job['candidates'][0]['qc'] = {'state': 'VALID', 'error': '/data/private secret'}
    store.save(job)
    text = web.get('/api/jobs/' + job['id']).text
    assert 'redis://' not in text and '/data/private' not in text and str(store.ROOT) not in text


def test_human_timeline_edit_and_frame_analysis_routes_are_artifact_bound(web, monkeypatch):
    import json
    from pathlib import Path
    from app import store, frame_analysis
    from app.artifacts import artifact_manifest, digest
    from app.timeline import build_timeline

    job = make_job()
    source = store.INPUT / 'authorized-source.mp4'
    source.write_bytes(b'source media')
    transcript = {'segments': [{'start': 0, 'end': 20, 'text': 'A complete conclusion.',
                                'words': [{'start': 1, 'end': 2, 'text': 'A'}]}]}
    clip = job['candidates'][0]
    clip.update(text='A complete conclusion.', timeline=build_timeline(clip, transcript['segments']))
    job['source'] = str(source)
    job['transcript_sha256'] = digest(transcript)
    store.JOBS.joinpath(f"{job['id']}.transcript.json").write_text(json.dumps(transcript), encoding='utf-8')
    Path(clip['timeline_file']).write_text(json.dumps(clip['timeline']), encoding='utf-8')
    clip['artifact_manifest'] = artifact_manifest(job, 0)
    clip['artifact_id'] = 'sha256:' + digest(clip['artifact_manifest'])
    store.save(job)
    cid = clip['candidate_id']
    frames_route = f"/api/jobs/{job['id']}/candidates/{cid}/frames"
    monkeypatch.setattr(frame_analysis, 'analyze_candidate_frames', lambda source, timeline: {
        'frames': [], 'vision': {'status': 'UNCONFIGURED'}})
    identity = {'artifact': clip['artifact_id'], 'candidate_version': clip['candidate_version'],
                'render_revision': clip['render_revision']}
    frame_response = web.post(frames_route, json=identity)
    assert frame_response.status_code == 200 and frame_response.json()['vision']['status'] == 'UNCONFIGURED'

    edit_response = web.post(f"/api/jobs/{job['id']}/candidates/{cid}/edit", json={
        **identity, 'editorial_revision': 0, 'request_id': str(uuid.uuid4()),
        'changes': {'title': 'Human confirmed title'},
    })
    assert edit_response.status_code == 200, edit_response.text
    revised = store.load(job['id'])
    assert revised['status'] == 'QUEUED'
    assert revised['candidates'][0]['timeline']['layers']['text'][0]['origin'] == 'human'
    assert revised['approved'] == []
    assert web.post(frames_route, json=identity).status_code == 409


def test_metrics_include_zero_grade_and_heartbeat_does_not_infer(web, monkeypatch):
    from app import doctor
    monkeypatch.setattr(doctor, 'snapshot', lambda _: {'worker': {'online': False}, 'ollama': {'reachable': False}})
    job = make_job()
    response, _ = request_review(web, job, payload={'dec': 'REJECTED', 'comment': 'not relevant',
        'reasons': [], 'adjust': '', 'rating': {'hook': 2}, 'grade': 0})
    assert response.status_code == 200
    metrics = web.get('/api/metrics').json()
    assert metrics['grades']['0'] == 1
    assert metrics['dimensions']['hook']['mean'] == 2
    health = web.get('/api/doctor').json()
    assert health['worker']['online'] is False and health['queue'] == 0


def test_unchanged_dashboard_reuses_projection_but_file_changes_invalidate(web, monkeypatch):
    from app import service, store
    job = make_job()
    original = service.get_editorial_view
    calls = []
    def project(j):
        calls.append(j['id'])
        return original(j)
    monkeypatch.setattr(service, 'get_editorial_view', project)
    web.get('/api/jobs/' + job['id'])
    web.get('/api/jobs/' + job['id'])
    assert len(calls) == 1
    from pathlib import Path
    Path(job['candidates'][0]['file']).write_bytes(b'changed bytes')
    assert web.get('/api/jobs/' + job['id']).json()['cands'][0]['intact'] is False
    assert len(calls) == 2


def test_schedule_rejects_missing_identity_past_time_and_unapproved(web):
    import time
    assert web.post('/api/publications/schedule', json={'rows': [{'pv': 'instagram', 'at': time.time() * 1000}],
                    'immediate': False}).status_code == 422
    job = make_job()
    row = {'pv': 'instagram', 't': 'test', 'at': (time.time() + 3600) * 1000,
           'job_id': job['id'], 'candidate_id': job['candidates'][0]['candidate_id'],
           'artifact': job['candidates'][0]['artifact_id'], 'caption': '', 'page_id': '123', 'instagram_id': '456'}
    assert web.post('/api/publications/schedule', json={'rows': [row], 'immediate': False}).status_code == 409
    assert web.post('/api/publications/schedule', json={'rows': [{**row, 'at': 1}], 'immediate': False}).status_code == 422


def test_local_publication_lifecycle_and_draft_identity(web, monkeypatch):
    import time
    from app import publication_schedule as agenda
    monkeypatch.setenv('CONTENT_FACTORY_META_ENABLED', 'true')
    job = make_job()
    assert request_review(web, job)[0].status_code == 200
    row = {'pv': 'instagram', 't': 'test', 'at': (time.time()+86400)*1000, 'job_id': job['id'],
           'candidate_id': job['candidates'][0]['candidate_id'], 'artifact': job['candidates'][0]['artifact_id'],
           'caption': '', 'page_id': '123', 'instagram_id': '456'}
    draft = {'pv': 'instagram', 'cand': row['candidate_id'], 'job_id': job['id'], 'artifact': 'old', 'title': 'test', 'desc': ''}
    assert web.post('/api/publications/drafts', json=draft).status_code == 409
    draft['artifact'] = row['artifact']
    assert web.post('/api/publications/drafts', json=draft).status_code == 200
    assert web.post('/api/publications/drafts', json={**draft, 'title': 'x'*256}).status_code == 422
    response = web.post('/api/publications/schedule', json={'rows': [row], 'immediate': False})
    assert response.status_code == 200, response.text
    pid = response.json()['id']
    assert web.post(f'/api/publications/{pid}/reschedule', json={'at':row['at']+3600000}).status_code == 200
    assert web.post(f'/api/publications/{pid}/cancel', json={}).status_code == 200
    assert web.post(f'/api/publications/{pid}/reschedule', json={'at':row['at']}).status_code == 409
    assert agenda.list_items()[0]['state'] == 'CANCELLED'


def test_schedule_identity_is_frozen_inside_its_service_lock(web):
    import time
    from app import publication_schedule as agenda
    job = make_job()
    assert request_review(web, job)[0].status_code == 200
    from app import store, service
    from app.artifacts import register_render
    updated = store.load(job['id'])
    register_render(updated, 0)
    store.save(updated)
    with pytest.raises(service.Conflict):
        agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'facebook', title='test', caption='',
                        scheduled_at=time.time()+86400, page_id='123', expected_artifact_id=job['candidates'][0]['artifact_id'])


def test_configured_publisher_enables_instagram_without_sharing_credentials(web, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.delenv('CONTENT_FACTORY_META_ENABLED', raising=False)
    agenda.ROOT.mkdir(parents=True)
    agenda.write_heartbeat(configured=True)
    state = web.get('/api/bootstrap').json()
    assert state['providers']['instagram']['can_schedule'] is True
    assert state['providers']['instagram']['worker_online'] is True
    assert 'token' not in str(state).lower()
    monkeypatch.setenv('CONTENT_FACTORY_META_ENABLED', 'false')
    assert web.get('/api/bootstrap').json()['providers']['instagram']['can_schedule'] is False


@pytest.mark.parametrize('link,expected', [
    ('https://www.instagram.com/reel/test/', 'https://www.instagram.com/reel/test/'),
    ('https://instagram.com.evil.test/reel/test/', None), ('javascript:alert(1)', None)])
def test_confirmed_publication_link_only_accepts_provider_https(link, expected):
    from app.web_views import item_view
    item = {'id': 'test', 'scheduled_at': 1, 'state': 'PUBLISHED', 'permalink': link,
            'draft': {'provider': 'instagram', 'title': 'test', 'job_id': 'j', 'candidate_id': 'c', 'artifact_id': 'a'}}
    assert item_view(item)['permalink'] == expected

