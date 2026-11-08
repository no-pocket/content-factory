import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

CLIENT=Path(__file__).resolve().parents[1]/'integrations/hermes/nopocket-content/skills/content-editorial/scripts/cf_editorial.py'
spec=importlib.util.spec_from_file_location('cf_editorial_client',CLIENT)
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


def test_client_refuses_redirect_instead_of_forwarding_credential():
    with pytest.raises(ValueError,match='Redirect refused'):
        client.NoRedirect().redirect_request(None,None,None,None,None,None)


def test_media_download_checks_candidate_checksum_before_returning_attachment(tmp_path,monkeypatch):
    import hashlib
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_TOKEN','synthetic-test-private-token-long-enough')
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_URL','http://127.0.0.1:18510')
    monkeypatch.setenv('CONTENT_FACTORY_MEDIA_CACHE',str(tmp_path))
    class Reply(io.BytesIO):
        def __init__(self,data,mime):
            super().__init__(data)
            from email.message import Message
            self.headers=Message();self.headers['Content-Type']=mime;self.headers['Content-Length']=str(len(data))
    class Opener:
        def open(self,request,timeout):
            if '/media?' in request.full_url:return Reply(b'replaced transport bytes','video/mp4')
            return Reply(json.dumps({'artifact_id':'sha256:'+'a'*64,'master_sha256':hashlib.sha256(b'original').hexdigest()}).encode(),'application/json')
    monkeypatch.setattr(client.urllib.request,'build_opener',lambda *args:Opener())
    args=SimpleNamespace(command='media',job='00000000-0000-0000-0000-000000000001',candidate='00000000-0000-0000-0000-000000000002',artifact_id='sha256:'+'a'*64)
    with pytest.raises(ValueError,match='checksum'):
        client.run(args)
    assert not list(tmp_path.glob('*.mp4'))
