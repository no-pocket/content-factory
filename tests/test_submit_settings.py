from app import store, submit
from app.job_settings import DEFAULTS
import json
from pathlib import Path


def test_submit_keeps_validated_settings_for_external_frontends(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    queued = []
    class Redis:
        def lpush(self, key, jid): queued.append(jid)
    monkeypatch.setattr(submit, 'rconn', lambda: Redis())
    result = submit.submit({
        'source_url': 'https://youtu.be/dQw4w9WgXcQ', 'creator': 'creator',
        'license_note': 'grant', 'rights_confirmed': True, 'platform_permission': True,
        'settings': {'clip_count': 4, 'target_seconds': 32},
    })
    job = store.load(result['job_id'])
    assert queued == [result['job_id']]
    assert job['settings']['clip_count'] == 4
    assert job['settings']['target_seconds'] == 32


def test_ingest_contract_lists_all_job_settings():
    contract = json.loads((Path(__file__).resolve().parents[1] / 'contracts' / 'youtube_ingest.schema.json').read_text())
    assert set(contract['properties']['settings']['properties']) == set(DEFAULTS)
