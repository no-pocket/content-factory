import copy
import hashlib
import json
import uuid

import pytest

from app import source_ingestion, source_registry, store
from test_source_ingestion import CHANNEL, URL, Queue, metadata, setup


def test_linked_attempt_preserves_parent_and_is_idempotent(setup):
    from app.editorial_attempt import create_attempt
    source_registry.upsert_source(dict(channel_id=CHANNEL, name='Canal', status='active',
        rights_confirmed=True, platform_permission=True, authorization_reference='Owner',
        allowed_languages=['pt'], allowed_video_kinds=['video', 'short'],
        allowed_model_scopes=['local', 'external']))
    q = Queue()
    parent = source_ingestion.ingest_youtube(setup, queue=q, metadata_fetcher=metadata)['job']
    media = store.INPUT / 'source.mp4'; media.write_bytes(b'video')
    parent.update(source=str(media), status='PARTIAL_FAILED', candidates=[{'state':'VALID'}],
                  source_fingerprint=hashlib.sha256(b'video').hexdigest())
    store.save(parent)
    (store.JOBS / (parent['id'] + '.transcript.json')).write_text(json.dumps({'language':'pt','segments':[]}))
    request_id = str(uuid.uuid4())
    before = copy.deepcopy(store.load(parent['id']))
    child = create_attempt(parent['id'], request_id, queue=q, metadata_fetcher=metadata)
    again = create_attempt(parent['id'], request_id, queue=q, metadata_fetcher=metadata)
    assert child['id'] == again['id']
    assert child['source_parent_job'] == parent['id']
    assert child['settings']['editorial_planner'] == 'hermes_first'
    assert child['candidates'] == [] and store.load(parent['id']) == before
    assert q.ids.count(child['id']) == 1
    assert (store.JOBS / (child['id'] + '.transcript.json')).is_file()
    media.write_bytes(b'changed')
    with pytest.raises(ValueError, match='fingerprint'):
        create_attempt(parent['id'], str(uuid.uuid4()), queue=q, metadata_fetcher=metadata)


def test_linked_attempt_requires_current_external_permission(setup):
    from app.editorial_attempt import create_attempt
    parent = source_ingestion.ingest_youtube(setup, queue=Queue(), metadata_fetcher=metadata)['job']
    parent['status'] = 'FAILED'; store.save(parent)
    with pytest.raises(PermissionError):
        create_attempt(parent['id'], str(uuid.uuid4()), queue=Queue(), metadata_fetcher=metadata)


def test_attempt_refuses_running_parent(setup):
    from app.editorial_attempt import create_attempt
    parent = source_ingestion.ingest_youtube(setup, queue=Queue(), metadata_fetcher=metadata)['job']
    with pytest.raises(ValueError, match='idle'):
        create_attempt(parent['id'], str(uuid.uuid4()), queue=Queue(), metadata_fetcher=metadata)
