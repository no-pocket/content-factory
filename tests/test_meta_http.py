import io
import json
import pytest

from app import meta_http


class Response:
    status = 200
    def read(self, size=-1):
        return b'{"id":"123"}'


class Connection:
    def __init__(self, host, timeout):
        self.host = host
        self.calls = []
        instances.append(self)
    def putrequest(self, method, path): self.calls.append(('request', method, path))
    def putheader(self, name, value): self.calls.append(('header', name, value))
    def endheaders(self): pass
    def send(self, data): self.calls.append(('body', data))
    def getresponse(self): return Response()
    def close(self): pass


instances = []


def test_http_client_uses_only_meta_hosts_and_auth_header(monkeypatch):
    instances.clear()
    monkeypatch.setattr(meta_http.http.client, 'HTTPSConnection', Connection)
    api = meta_http.MetaHTTP('v27.0')
    assert api('POST', 'upload/123', 'secret', file=io.BytesIO(b'video'), headers={'offset': '0', 'file_size': '5'}) == {'id': '123'}
    conn = instances[-1]
    assert conn.host == 'rupload.facebook.com'
    assert ('header', 'Authorization', 'OAuth secret') in conn.calls
    assert all('secret' not in str(call) for call in conn.calls if call[0] == 'request')
    assert ('body', b'video') in conn.calls


@pytest.mark.parametrize('path', ['https://evil.example/123', 'upload/123/../../x', 'me/accounts?access_token=bad'])
def test_http_client_rejects_unexpected_paths(path):
    with pytest.raises(ValueError):
        meta_http.MetaHTTP('v27.0')('GET', path, 'secret')


def test_http_client_does_not_expose_remote_error(monkeypatch):
    class BadResponse(Response):
        status = 400
        def read(self, size=-1): return b'{"error":{"message":"secret"}}'
    class BadConnection(Connection):
        def getresponse(self): return BadResponse()
    monkeypatch.setattr(meta_http.http.client, 'HTTPSConnection', BadConnection)
    with pytest.raises(meta_http.MetaHTTPError) as exc:
        meta_http.MetaHTTP('v27.0')('POST', '123/media', 'secret', params={'caption': 'x'})
    assert 'secret' not in str(exc.value)


def test_page_credentials_must_match_scheduled_instagram_account():
    from app.meta_http import resolve_page
    def api(method, path, token):
        assert token == 'user-token'
        return {'id': '123', 'access_token': 'page-token',
                'instagram_business_account': {'id': '456'}}
    assert resolve_page(api, '123', '456', 'user-token') == 'page-token'
    with pytest.raises(ValueError):
        resolve_page(api, '123', '789', 'user-token')
