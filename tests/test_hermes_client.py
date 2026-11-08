import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

CLIENT=Path(__file__).resolve().parents[1]/'integrations/hermes/nopocket-content/skills/content-editorial/scripts/cf_editorial.py'
spec=importlib.util.spec_from_file_location('cf_editorial_client',CLIENT)
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


def test_client_loads_only_its_own_profile_env_without_exporting_secrets(tmp_path,monkeypatch):
    profile=tmp_path/'profiles'/'nopocket-content'
    script=profile/'skills/content-editorial/scripts/cf_editorial.py'
    script.parent.mkdir(parents=True)
    (profile/'.env').write_text('CONTENT_FACTORY_HERMES_URL=http://127.0.0.1:18510\n'
        'CONTENT_FACTORY_HERMES_TOKEN="synthetic-profile-token-long-enough"\n'
        'CONTENT_FACTORY_MEDIA_CACHE=/private/profile/media\nUNRELATED_SECRET=ignored\n')
    (tmp_path/'.env').write_text('CONTENT_FACTORY_HERMES_TOKEN=wrong-global-token\n')
    monkeypatch.setattr(client,'__file__',str(script))
    for key in ('CONTENT_FACTORY_HERMES_URL','CONTENT_FACTORY_HERMES_TOKEN','CONTENT_FACTORY_MEDIA_CACHE'):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    assert client.config()==('http://127.0.0.1:18510','synthetic-profile-token-long-enough')
    assert client.settings()['CONTENT_FACTORY_MEDIA_CACHE']=='/private/profile/media'
    assert 'UNRELATED_SECRET' not in client.settings()
    assert 'CONTENT_FACTORY_HERMES_TOKEN' not in client.os.environ
    (profile/'.env').unlink()
    with pytest.raises(ValueError,match='credential not configured'):
        client.config()


def test_explicit_environment_overrides_profile_configuration(tmp_path,monkeypatch):
    script=tmp_path/'skills/content-editorial/scripts/cf_editorial.py'
    script.parent.mkdir(parents=True)
    (tmp_path/'.env').write_text('CONTENT_FACTORY_HERMES_TOKEN=synthetic-profile-token-long-enough\n')
    monkeypatch.setattr(client,'__file__',str(script))
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_TOKEN','synthetic-explicit-token-long-enough')
    monkeypatch.setenv('CONTENT_FACTORY_HERMES_URL','http://127.0.0.1:18511')
    assert client.config()==('http://127.0.0.1:18511','synthetic-explicit-token-long-enough')


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

@pytest.mark.parametrize('command,expected', [('sources','/sources'), ('status','/jobs/00000000-0000-0000-0000-000000000001'), ('ingest','/ingest')])
def test_ingestion_routes(command, expected):
    args = SimpleNamespace(command=command, job='00000000-0000-0000-0000-000000000001')
    assert client.route(args) == expected
