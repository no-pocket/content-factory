from app import store, source_ingestion as ingestion
from test_source_ingestion import Queue, URL, CHANNEL, metadata, setup

def test_hermes_import_does_not_require_registered_channel(setup):
    (store.ROOT / 'sources.json').unlink()
    result=ingestion.ingest_youtube(setup,queue=Queue(),metadata_fetcher=lambda u:{**metadata(u),'language':None},enforce_source_policy=False)
    job=result['job']
    assert job['source_snapshot']['channel_id']==CHANNEL
    assert job['source_snapshot']['policy_mode']=='not_enforced'
    assert job['platform_permission'] is False
    assert job['source_snapshot'].get('rights_confirmed') is not True
    assert job['source_snapshot']['allowed_model_scopes']==['local','external']

def test_hermes_unrestricted_still_checks_identity_and_live(setup):
    import pytest
    from app import hermes_api, editorial_requests
    job=ingestion.ingest_youtube(setup,queue=Queue(),metadata_fetcher=metadata,enforce_source_policy=False)['job']
    source=job['source_snapshot']
    assert hermes_api._external_allowed(job)
    editorial_requests.authorize_local_source(job)
    for change in ({'channel_id':'UC'+'b'*22},{'id':'invalid'},{'is_live':True}):
        with pytest.raises((PermissionError,ValueError)):
            ingestion.verify_source_metadata({**metadata(URL),**change},'g8Q1UxPJulc',source,{})

def test_hermes_unrestricted_duplicate_reuses_job(setup):
    queue=Queue()
    first=ingestion.ingest_youtube(setup,queue=queue,metadata_fetcher=metadata,enforce_source_policy=False)
    second=ingestion.ingest_youtube(setup,queue=queue,metadata_fetcher=metadata,enforce_source_policy=False)
    assert second['duplicate'] is True
    assert second['job']['id']==first['job']['id']
    assert len(queue.ids)==1
