import io
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

from app import api, service, store


def test_http_auth_contract_review_conflict_and_paths(monkeypatch, tmp_path):
    monkeypatch.setenv('CONTENT_FACTORY_API_TOKEN', 'test-token-long-enough')
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    monkeypatch.setattr(store, 'INPUT', tmp_path)
    monkeypatch.setattr(service, 'verify_reviewable', lambda *a: True)
    monkeypatch.setattr(store, 'rconn', lambda: type('Queue', (), {'lpush': lambda *a: None})())
    server = HTTPServer(('127.0.0.1', 0), api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, payload=None, auth=True):
        headers = {'Authorization': 'Bearer test-token-long-enough'} if auth else {}
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path,
                                     data=json.dumps(payload).encode() if payload is not None else None,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)
    try:
        assert request('/v1/jobs', auth=False)[0] == 401
        assert request('/v1/jobs', {'source': '/etc/passwd'})[0] == 422
        status, job = request('/v1/jobs', {'source_url': 'https://youtu.be/dQw4w9WgXcQ',
                                         'creator': 'Canal', 'license_note': 'grant',
                                         'rights_confirmed': True, 'platform_permission': True})
        assert status == 201
        jid = job['id']
        assert 'source' not in job
        assert request('/v1/jobs/' + jid)[0] == 200
        assert request('/v1/jobs/' + jid + '/candidates/0/media/mp4')[0] == 422
        assert request('/v1/jobs/no-such-id')[0] == 404
        assert request('/v1/jobs/' + jid + '/review', {'expected_revision': 0, 'decisions': []})[0] == 409
        # Synthetic HTTP review: rejection is allowed without media QC, approval is not.
        saved = store.load(jid)
        saved.update(status='PARTIAL_FAILED', candidates=[
            {'start': 0, 'end': 20, 'state': 'FAILED'},
            {'start': 20, 'end': 40, 'state': 'VALID'}])
        store.save(saved)
        monkeypatch.setattr(service, 'verify_reviewable', lambda *a: False)
        route = '/v1/jobs/' + jid + '/candidates/0/review'
        payload = {'decision': 'REJECTED', 'reason': 'Synthetic rejection comment', 'expected_revision': 0}
        status, reviewed = request(route, payload)
        assert status == 200 and reviewed['status'] == 'PARTIAL_FAILED'
        decision = reviewed['decision_history'][-1]['decisions'][0]
        assert decision['reason'] == payload['reason'] and decision['hook'] is None
        assert request(route, payload)[0] == 409  # Optimistic revision still applies.
        assert request(route, {**payload, 'expected_revision': 1, 'decision': 'APPROVED'})[0] == 409
        status, rejected = request('/v1/jobs/' + jid + '/reject', {'reason': 'Synthetic whole-job rejection'})
        assert status == 200 and rejected['status'] == 'REJECTED'
        assert len(rejected['decision_history']) == 2 and rejected['approved'] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
