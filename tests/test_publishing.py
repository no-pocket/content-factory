import json
from pathlib import Path

import pytest

from app import service, store
from test_editorial_service_v2 import v2job, review_request


def approved(job):
    service.review_candidate_v2(job['id'], job['candidates'][0]['candidate_id'], review_request(job))
    return store.load(job['id'])


def test_only_current_fully_approved_artifact_can_be_drafted(v2job):
    from app.publishing import build_draft
    cid = v2job['candidates'][0]['candidate_id']
    with pytest.raises(service.Conflict):
        build_draft(v2job, cid, 'youtube', title='Synthetic')
    job = approved(v2job)
    draft = build_draft(job, cid, 'youtube', title='Synthetic')
    assert draft['artifact_id'] == job['candidates'][0]['artifact_id']
    Path(job['candidates'][0]['file']).write_bytes(b'replaced master!')
    with pytest.raises(service.Conflict):
        build_draft(job, cid, 'youtube', title='Synthetic')


def test_adjustments_and_legacy_approvals_never_qualify(v2job):
    from app.publishing import build_draft
    cid = v2job['candidates'][0]['candidate_id']
    service.review_candidate_v2(v2job['id'], cid, review_request(v2job, decision='APPROVED_WITH_ADJUSTMENTS'))
    with pytest.raises(service.Conflict):
        build_draft(store.load(v2job['id']), cid, 'tiktok', title='Synthetic')
    v2job.update(editorial_protocol=1, approved=[0])
    with pytest.raises(service.Conflict):
        build_draft(v2job, cid, 'youtube', title='Synthetic')


def test_outbox_is_local_idempotent_secret_free(v2job, tmp_path, monkeypatch):
    from app import publishing as p
    monkeypatch.setattr(p, 'ROOT', tmp_path/'publishing')
    monkeypatch.setenv('YOUTUBE_ACCESS_TOKEN', 'never-store-this-secret')
    job = approved(v2job)
    args = (job['id'], job['candidates'][0]['candidate_id'], 'youtube')
    first = p.queue_dry_run(*args, title='Synthetic')
    assert p.queue_dry_run(*args, title='Synthetic') == first
    assert first['state'] == 'DRY_RUN' and first['remote_id'] is None
    assert 'never-store-this-secret' not in json.dumps(first)
    assert len(list(p.ROOT.glob('*.json'))) == 1


@pytest.mark.parametrize('provider,edge', [('instagram','/media'), ('facebook','/video_reels'), ('youtube','/videos'), ('tiktok','/video/init/')])
def test_provider_specific_plans(provider, edge):
    from app.publishing_adapters import request_plan
    plan = request_plan(provider, title='Synthetic', description='Caption', size=123)
    assert edge in plan['steps'][0]['endpoint']
    assert plan['executable'] is False
    assert 'Authorization' not in json.dumps(plan)


def test_configured_credentials_are_not_connected(monkeypatch):
    from app.publishing import connection_status
    monkeypatch.setenv('YOUTUBE_ACCESS_TOKEN', 'secret')
    monkeypatch.setenv('YOUTUBE_CHANNEL_ID', 'channel')
    row = connection_status('youtube')
    assert row['state'] == 'CONFIGURED_UNVERIFIED'
    assert 'secret' not in json.dumps(row)


def test_bad_provider_and_title_rejected(v2job):
    from app.publishing import build_draft
    job = approved(v2job); cid = job['candidates'][0]['candidate_id']
    with pytest.raises(ValueError): build_draft(job, cid, '../escape', title='Synthetic')
    with pytest.raises(ValueError): build_draft(job, cid, 'youtube', title='x'*101)


def test_fresh_qc_failure_blocks_draft(v2job, monkeypatch):
    from app.publishing import build_draft
    job = approved(v2job)
    monkeypatch.setattr(service, 'verify_reviewable', lambda *args: False)
    with pytest.raises(service.Conflict, match='QC'):
        build_draft(job, job['candidates'][0]['candidate_id'], 'youtube', title='Synthetic')


def test_outside_job_artifact_path_is_rejected(v2job, tmp_path):
    from app.publishing import build_draft
    job = approved(v2job)
    outside = tmp_path / 'outside.mp4'; outside.write_bytes(b'outside')
    job['candidates'][0]['file'] = str(outside)
    with pytest.raises(ValueError, match='outside'):
        build_draft(job, job['candidates'][0]['candidate_id'], 'facebook', title='Synthetic')
