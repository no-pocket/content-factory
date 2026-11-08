from concurrent.futures import ThreadPoolExecutor
import pytest
from app import store, source_registry as registry, source_ingestion as ingestion

CHANNEL = 'UC' + 'a' * 22
URL = 'https://youtu.be/g8Q1UxPJulc'

class Queue:
    def __init__(self): self.ids = []
    def lpush(self, key, value): self.ids.append(value)
    def eval(self, script, count, pending, processing, jid):
        if jid in self.ids or jid in getattr(self,'processing',[]): return 0
        self.lpush(pending,jid)
        return 1

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    for key in ('JOBS', 'INPUT', 'OUTPUT'):
        folder = tmp_path / key.lower(); folder.mkdir()
        monkeypatch.setattr(store, key, folder)
    monkeypatch.setenv('ENABLE_YOUTUBE_DOWNLOAD', 'true')
    registry.upsert_source(dict(channel_id=CHANNEL, name='Canal', status='active',
        rights_confirmed=True, platform_permission=True, authorization_reference='Owner authorization',
        allowed_languages=['pt'], allowed_video_kinds=['video', 'short']))
    return dict(source_url=URL)

def metadata(url):
    return dict(id='g8Q1UxPJulc', channel_id=CHANNEL, title='Vídeo', language='pt', live_status='not_live')

def test_verified_metadata_and_concurrent_dedup(setup):
    q = Queue()
    def submit(_): return ingestion.ingest_youtube(setup, queue=q, metadata_fetcher=metadata)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert len(q.ids) == 1
    assert len({r['job']['id'] for r in results}) == 1
    job = results[0]['job']
    assert job['source_snapshot']['channel_id'] == CHANNEL
    assert job['youtube_metadata']['video_id'] == 'g8Q1UxPJulc'
    assert len(store.all_jobs()) == 1

@pytest.mark.parametrize('change', [{'channel_id':'UC'+'b'*22}, {'language':None}, {'is_live':True}])
def test_metadata_denied_before_job(setup, change):
    with pytest.raises((ValueError, PermissionError)):
        ingestion.ingest_youtube(setup, queue=Queue(), metadata_fetcher=lambda u: {**metadata(u), **change})
    assert store.all_jobs() == []

def test_pending_source_and_disabled_installation_deny(setup, monkeypatch):
    monkeypatch.setenv('ENABLE_YOUTUBE_DOWNLOAD', 'false')
    with pytest.raises(PermissionError):
        ingestion.ingest_youtube(setup, queue=Queue(), metadata_fetcher=metadata)
    monkeypatch.setenv('ENABLE_YOUTUBE_DOWNLOAD', 'true')
    registry.upsert_source(dict(channel_id=CHANNEL, name='Canal'))
    with pytest.raises(PermissionError):
        ingestion.ingest_youtube(setup, queue=Queue(), metadata_fetcher=metadata)

def test_queue_failure_keeps_one_recoverable_job(setup):
    class Broken:
        def lpush(self, *a): raise OSError('offline')
    with pytest.raises(RuntimeError):
        ingestion.ingest_youtube(setup, queue=Broken(), metadata_fetcher=metadata)
    saved = store.all_jobs()[0]
    assert saved['status'] == 'QUEUE_FAILED'
    q = Queue()
    result = ingestion.ingest_youtube(setup, queue=q, metadata_fetcher=metadata)
    assert result['job']['id'] == saved['id']
    assert q.ids == [saved['id']]
    assert len(store.all_jobs()) == 1

def test_ambiguous_kind_and_forged_model_scope_fail_closed(setup):
    registry.upsert_source(dict(channel_id=CHANNEL,name='Canal',status='active',rights_confirmed=True,
        platform_permission=True,authorization_reference='Owner',allowed_languages=['pt'],allowed_video_kinds=['video']))
    with pytest.raises(PermissionError,match='kind'):
        ingestion.ingest_youtube(setup,queue=Queue(),metadata_fetcher=metadata)
    with pytest.raises(ValueError):
        ingestion.ingest_youtube({**setup,'model_scope':'local'},queue=Queue(),metadata_fetcher=metadata)

def test_downloader_rechecks_channel_before_any_media(setup, monkeypatch, tmp_path):
    import sys, types
    from app.youtube import download_youtube
    calls=[]
    class FakeYDL:
        def __init__(self,options): self.params=options
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def extract_info(self,url,download=False):
            calls.append(download)
            return {**metadata(url),'channel_id':'UC'+'b'*22}
    monkeypatch.setitem(sys.modules,'yt_dlp',types.SimpleNamespace(YoutubeDL=FakeYDL))
    with pytest.raises(PermissionError,match='channel'):
        download_youtube(URL,tmp_path,source_snapshot=registry.get_source(CHANNEL),settings={})
    assert calls == [False]

def test_downloader_rechecks_second_extraction_and_revocation(setup, monkeypatch, tmp_path):
    import sys, types
    from app.youtube import download_youtube
    source = registry.get_source(CHANNEL)
    calls=[]
    class FakeYDL:
        def __init__(self,options): self.params=options
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def extract_info(self,url,download=False):
            if download:
                self.params['match_filter']({**metadata(url),'channel_id':'UC'+'b'*22},incomplete=False)
                calls.append('media')
            return metadata(url)
    monkeypatch.setitem(sys.modules,'yt_dlp',types.SimpleNamespace(YoutubeDL=FakeYDL))
    with pytest.raises(PermissionError,match='channel'):
        download_youtube(URL,tmp_path,source_snapshot=source,settings={})
    assert calls == []
    registry.upsert_source(dict(channel_id=CHANNEL,name='Revoked',status='disabled'))
    with pytest.raises(PermissionError):
        download_youtube(URL,tmp_path,source_snapshot=source,settings={})
    assert calls == []

def test_snapshot_and_local_model_policy(setup):
    q=Queue()
    job=ingestion.ingest_youtube(setup,queue=q,metadata_fetcher=metadata)['job']
    registry.upsert_source(dict(channel_id=CHANNEL,name='Changed',status='pending'))
    assert store.load(job['id'])['source_snapshot']['status'] == 'active'
    external={k:'external' for k in ('ranker_mode','director_mode','llm_backend','llm_model')}
    with pytest.raises(PermissionError,match='Model scope'):
        ingestion.verify_source_metadata(metadata(URL),'g8Q1UxPJulc',job['source_snapshot'],external)

def test_process_crash_after_save_recovers_without_worker_restart(setup, monkeypatch):
    original = ingestion.service.enqueue
    def crash(*a,**k): raise SystemExit('process stopped before queue write')
    monkeypatch.setattr(ingestion.service,'enqueue',crash)
    with pytest.raises(SystemExit):
        ingestion.ingest_youtube(setup,queue=Queue(),metadata_fetcher=metadata)
    saved=store.all_jobs()[0]
    assert saved['status'] == 'QUEUED'
    monkeypatch.setattr(ingestion.service,'enqueue',original)
    q=Queue()
    recovered=ingestion.ingest_youtube(setup,queue=q,metadata_fetcher=metadata)
    assert recovered['job']['id'] == saved['id']
    assert q.ids == [saved['id']]
    ingestion.ingest_youtube(setup,queue=q,metadata_fetcher=metadata)
    assert q.ids == [saved['id']]
    q.ids.clear(); q.processing=[saved['id']]
    ingestion.ingest_youtube(setup,queue=q,metadata_fetcher=metadata)
    assert q.ids == []

def test_revoked_source_stops_cached_media_before_processing(setup, monkeypatch, tmp_path):
    from app import worker
    job=ingestion.ingest_youtube(setup,queue=Queue(),metadata_fetcher=metadata)['job']
    media=tmp_path/'cached.mp4'; media.write_bytes(b'cached')
    job['source']=str(media); store.save(job)
    registry.upsert_source(dict(channel_id=CHANNEL,name='Revoked',status='disabled'))
    monkeypatch.setattr(worker,'get_duration',lambda *a: pytest.fail('Processing revoked source'))
    worker.process(job['id'])
    assert store.load(job['id'])['status'] == 'FAILED'

def test_external_plan_cannot_be_created_by_url_ingestion(setup):
    registry.upsert_source(dict(channel_id=CHANNEL,name='Canal',status='active',rights_confirmed=True,
        platform_permission=True,authorization_reference='Owner',allowed_languages=['pt'],
        allowed_model_scopes=['local','external']))
    external={k:'external' for k in ('ranker_mode','director_mode','llm_backend','llm_model')}
    q=Queue()
    with pytest.raises(ValueError,match='External plans'):
        ingestion.ingest_youtube({**setup,'settings':external},queue=q,metadata_fetcher=metadata)
    assert q.ids == []
    assert store.all_jobs() == []
