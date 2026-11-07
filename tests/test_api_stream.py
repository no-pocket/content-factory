"""Raw upload contract with synthetic bytes and no worker processing."""
import base64
import hashlib
import http.client
import json
import threading
from http.server import HTTPServer

from app import api, store


def test_streaming_upload_exceeds_json_limit_and_preserves_utf8(monkeypatch, tmp_path):
    monkeypatch.setenv('CONTENT_FACTORY_API_TOKEN', 'synthetic-token-long-enough')
    monkeypatch.setattr(store, 'JOBS', tmp_path / 'work')
    monkeypatch.setattr(store, 'INPUT', tmp_path / 'input')
    store.JOBS.mkdir(); store.INPUT.mkdir()
    monkeypatch.setattr(api, 'MAX_BODY', 32)
    monkeypatch.setattr(api, 'MAX_UPLOAD_BODY', 8192)
    queued = []
    monkeypatch.setattr(store, 'rconn', lambda: type('Queue', (), {'lpush': lambda self, key, jid: queued.append(jid)})())
    server = HTTPServer(('127.0.0.1', 0), api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(body, metadata, *, length=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        connection.putrequest('POST', '/v1/jobs/upload')
        connection.putheader('Authorization', 'Bearer synthetic-token-long-enough')
        connection.putheader('Content-Type', 'application/octet-stream')
        connection.putheader('X-Content-Factory-Metadata', base64.b64encode(json.dumps(metadata, ensure_ascii=False).encode()).decode())
        connection.putheader('Content-Length', str(len(body) if length is None else length))
        connection.endheaders(body)
        if length is not None and length > len(body):
            connection.sock.shutdown(1)  # deterministic premature EOF
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result
    metadata = {'filename': 'português.mp4', 'creator': 'SYNTHETIC FIXTURE',
                'license_note': 'Synthetic fixture only', 'rights_confirmed': True}
    try:
        content = b'synthetic' * 512
        status, reply = request(content, metadata)
        assert status == 201
        job = store.load(reply['id'])
        assert job['original_name'] == 'português.mp4'
        assert job['source_fingerprint'] == hashlib.sha256(content).hexdigest()
        assert queued == [job['id']]
        assert request(b'x'*8193, metadata)[0] == 413
        assert request(b'x', {**metadata, 'rights_confirmed': False})[0] == 403
        assert request(b'x', {**metadata, 'source_url': 'https://youtu.be/dQw4w9WgXcQ'})[0] == 422
        assert request(b'partial', metadata, length=100)[0] == 422
        assert len(list(store.INPUT.iterdir())) == 1  # no truncated/unlicensed upload left behind
    finally:
        server.shutdown(); server.server_close(); thread.join()
