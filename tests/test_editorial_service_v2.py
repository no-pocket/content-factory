import copy
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import service, store
from app.editorial_contracts import candidate_key


@pytest.fixture
def v2job(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path / 'work')
    monkeypatch.setattr(store, 'OUTPUT', tmp_path / 'output')
    store.JOBS.mkdir()
    monkeypatch.setattr(service, 'verify_reviewable', lambda *args: True)
    job = store.new_job(None, 'SYNTHETIC', 'test', 'grant')
    folder = store.OUTPUT / job['id']
    folder.mkdir(parents=True)
    master = folder / 'candidate_1.mp4'
    master.write_bytes(b'synthetic master')
    master.with_suffix('.preview.webm').write_bytes(b'synthetic preview')
    master.with_suffix('.timeline.json').write_text('{}')
    job.update(editorial_protocol=2, status='NEEDS_REVIEW', candidates=[{
        'start': 0, 'end': 20, 'state': 'VALID', 'file': str(master),
        'timeline_file': str(master.with_suffix('.timeline.json'))}])
    from app.artifacts import register_render
    register_render(job, 0)
    store.save(job)
    return job


def review_request(job, **updates):
    return {'request_id': str(uuid.uuid4()), 'expected_editorial_revision': job.get('editorial_revision', 0),
            'expected_artifact_id': job['candidates'][0]['artifact_id'], 'decision': 'APPROVED',
            'comment_raw': 'SYNTHETIC: pronto', **updates}


def test_stale_artifact_rejected_without_new_human_event(v2job):
    request = review_request(v2job)
    from pathlib import Path
    Path(v2job['candidates'][0]['file']).write_bytes(b'replaced synthetic master')
    with pytest.raises(service.Conflict):
        service.review_candidate_v2(v2job['id'], candidate_key(v2job['id'], 0), request)
    assert store.load(v2job['id']).get('feedback_events', []) == []


def test_duplicate_request_is_idempotent(v2job):
    request = review_request(v2job)
    cid = candidate_key(v2job['id'], 0)
    first = service.review_candidate_v2(v2job['id'], cid, request)
    assert service.review_candidate_v2(v2job['id'], cid, request) == first
    assert len(store.load(v2job['id'])['feedback_events']) == 1
    with pytest.raises(service.Conflict):
        service.review_candidate_v2(v2job['id'], cid, {**request, 'comment_raw': 'changed'})


def test_concurrent_reviews_one_wins(v2job):
    cid = candidate_key(v2job['id'], 0)
    def attempt(_):
        try:
            service.review_candidate_v2(v2job['id'], cid, review_request(v2job))
            return 'saved'
        except service.Conflict:
            return 'conflict'
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ['conflict', 'saved']
    assert len(store.load(v2job['id'])['feedback_events']) == 1


def test_v1_cannot_bypass_v2(v2job):
    with pytest.raises(service.Conflict, match='editorial_protocol_required'):
        service.review_candidate(v2job['id'], 0, 'APPROVED', 'SYNTHETIC', expected_revision=0)
    with pytest.raises(service.Conflict, match='editorial_protocol_required'):
        service.reject_job(v2job['id'], 'SYNTHETIC')


def test_write_failure_preserves_previous_record(v2job, monkeypatch):
    before = store.load(v2job['id'])
    def fail(_):
        raise OSError('synthetic write failure')
    monkeypatch.setattr(store, 'save', fail)
    with pytest.raises(OSError):
        service.review_candidate_v2(v2job['id'], candidate_key(v2job['id'], 0), review_request(v2job))
    assert store.load(v2job['id']) == before


def test_new_render_preserves_history_and_revokes_current_decision(v2job):
    from app.artifacts import register_render
    cid = candidate_key(v2job['id'], 0)
    request = review_request(v2job)
    service.review_candidate_v2(v2job['id'], cid, request)
    job = store.load(v2job['id'])
    previous = copy.deepcopy(job['feedback_events'])
    register_render(job, 0)
    store.save(job)
    assert job['candidates'][0]['render_revision'] == 2
    assert job['feedback_events'] == previous
    view = service.get_editorial_view(job)
    assert view['candidates'][0]['normalized_decision'] == 'PENDING'
    with pytest.raises(service.Conflict):
        service.review_candidate_v2(job['id'], cid, review_request(v2job))


def test_rejection_allowed_for_failed_media(v2job, monkeypatch):
    monkeypatch.setattr(service, 'verify_reviewable', lambda *args: False)
    cid = candidate_key(v2job['id'], 0)
    with pytest.raises(service.Conflict):
        service.review_candidate_v2(v2job['id'], cid, review_request(v2job))
    result = service.review_candidate_v2(v2job['id'], cid, review_request(
        v2job, decision='REJECTED', rejection_domain='TECHNICAL', comment_raw='SYNTHETIC: arquivo falhou'))
    assert result['event']['decision'] == 'REJECTED'


def test_client_cannot_forge_human_actor(v2job):
    with pytest.raises(ValueError):
        service.review_candidate_v2(v2job['id'], candidate_key(v2job['id'], 0),
                                    review_request(v2job, actor={'id': 'someone-else'}))


def test_new_render_paths_are_backend_owned(v2job):
    from app.artifacts import artifact_manifest, render_target
    assert render_target(v2job, 0).relative_to(store.OUTPUT).parts[-2:] == ('render_2', 'master.mp4')
    job = copy.deepcopy(v2job)
    job['candidates'][0]['file'] = '/etc/passwd'
    with pytest.raises(ValueError):
        artifact_manifest(job, 0)


def test_changed_proposal_increments_candidate_version(v2job):
    from app.artifacts import register_render
    job = copy.deepcopy(v2job)
    job['candidates'][0]['end'] = 21
    register_render(job, 0)
    assert job['candidates'][0]['candidate_version'] == 2
    assert job['candidates'][0]['render_history'][0]['candidate_version'] == 1
