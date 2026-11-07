import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
import uuid

from app import api, service, store
from test_editorial_service_v2 import v2job, review_request


def test_api_v2_review_and_v1_protocol_guard(v2job, monkeypatch):
    monkeypatch.setenv('CONTENT_FACTORY_API_TOKEN', 'synthetic-test-token-long-enough')
    server = HTTPServer(('127.0.0.1', 0), api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def call(path, payload=None):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization': 'Bearer synthetic-test-token-long-enough', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    try:
        jid = v2job['id']
        status, view = call('/v2/jobs/' + jid)
        assert status == 200
        assert 'source' not in view
        assert 'file' not in view['candidates'][0]
        cid = view['editorial']['candidates'][0]['candidate_id']
        assert call(f'/v1/jobs/{jid}/candidates/0/review',
                    {'decision': 'APPROVED', 'reason': 'SYNTHETIC', 'expected_revision': 0}) == (
                        409, {'error': {'code': 'editorial_protocol_required', 'message': 'editorial_protocol_required'}})
        route = f'/v2/jobs/{jid}/candidates/{cid}/reviews'
        request = review_request(v2job)
        status, result = call(route, request)
        assert status == 200
        assert result['event']['actor']['channel'] == 'api'
        assert call(route, request) == (200, result)
        assert call(route, {**request, 'request_id': str(uuid.uuid4())})[0] == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_protocol_opt_in_saved_per_job(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    job = store.new_job(None, 'synthetic', 'test', 'grant', settings={'editorial_protocol': 2})
    assert store.load(job['id'])['editorial_protocol'] == 2
    assert store.new_job(None, 'legacy', 'test', 'grant')['editorial_protocol'] == 1
