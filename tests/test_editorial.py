import pytest
from app import service, store
from app.editorial import summarize


def record(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    monkeypatch.setattr(service, 'verify_reviewable', lambda job, idx: True)
    job = store.new_job(tmp_path / 'source.mp4', 'video', 'creator', 'grant')
    job.update(status='NEEDS_REVIEW', candidates=[{'state': 'VALID', 'start': 1, 'end': 20}])
    store.save(job)
    return job


def decision(approved=True):
    return {'candidate': 0, 'decision': 'APPROVED' if approved else 'REJECTED',
            'reason': 'Fechamento completo' if approved else 'Sem contexto',
            'hook': 4, 'context': 3, 'closure': 5, 'captions': 4,
            'rework': True, 'adjustments': 'Ajustar legenda'}


def test_reviews_preserve_history_and_conflicts(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    first = service.review_job(job['id'], [decision()], expected_revision=0)
    assert first['approved'] == [0]
    with pytest.raises(service.Conflict):
        service.review_job(job['id'], [decision(False)], expected_revision=0)
    second = service.review_job(job['id'], [decision(False)], expected_revision=1)
    assert len(second['decision_history']) == 2
    assert second['decision_history'][0]['settings'] == job['settings']
    assert second['approved'] == []
    report = summarize([second])
    assert report['reviewed_videos'] == 1
    assert report['approved_per_video'] == 0
    assert report['rework_rate'] == 1


def test_reject_invalid_review_and_failed_candidate(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    value = decision()
    value['hook'] = 6
    with pytest.raises(ValueError):
        service.review_job(job['id'], [value], expected_revision=0)
    job['candidates'][0]['state'] = 'FAILED'
    store.save(job)
    with pytest.raises(service.Conflict):
        service.review_job(job['id'], [decision()], expected_revision=0)


def test_metrics_deduplicate_source_and_exclude_unreviewed(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    reviewed = service.review_job(job['id'], [decision()], expected_revision=0)
    duplicate = {**reviewed, 'id': 'another-run'}
    pending = {**job, 'id': 'pending', 'source': 'another-video'}
    metrics = summarize([reviewed, duplicate, pending])
    assert metrics['reviewed_videos'] == 1
    assert metrics['approved_per_video'] == 1
    assert metrics['unreviewed_jobs'] == 1


def test_different_configurations_are_not_extra_videos(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    first = service.review_job(job['id'], [decision()], expected_revision=0)
    second = {**first, 'id': 'variant', 'settings': {**first['settings'], 'llm_backend': 'kepler_gpu'}}
    metrics = summarize([first, second])
    assert metrics['reviewed_videos'] == 1
    assert metrics['video_configuration_pairs'] == 2


def test_qc_failure_archives_current_approval(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    service.review_job(job['id'], [decision()], expected_revision=0)
    monkeypatch.setattr(service, 'inspect_candidate', lambda *a: {'state': 'FAILED'})
    checked = service.verify_existing(job['id'])
    assert checked['approved'] == []
    assert checked['decision_history'][0]['decisions'][0]['decision'] == 'APPROVED'


def test_refinement_is_evidence_limited_and_pairs_same_sources(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    baseline = service.review_job(job['id'], [decision()], expected_revision=0)
    variant = {**baseline, 'id': 'variant', 'settings': {**baseline['settings'], 'llm_backend': 'kepler_gpu'}}
    metrics = summarize([baseline, variant])
    assert metrics['paired_comparisons'][0]['paired_videos'] == 1
    assert metrics['paired_comparisons'][0]['approval_delta_per_video'] == 0
    assert metrics['refinement']['sufficient_for_general_rule'] is False
    assert metrics['refinement']['automatic_selection_update'] is False


def test_invalidated_decision_is_history_until_new_review(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    reviewed = service.review_job(job['id'], [decision()], expected_revision=0)
    reviewed['processing_runs'] = [{'started_at': 10, 'last_checkpoint_at': 12, 'state': 'RUNNING'}]
    service.invalidate_approvals(reviewed, {0})
    report = summarize([reviewed])
    assert report['reviewed_videos'] == 0
    assert report['unreviewed_jobs'] == 1


def test_metrics_separate_detected_languages(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    portuguese = service.review_job(job['id'], [decision()], expected_revision=0)
    portuguese['language'] = 'pt'
    english = {**portuguese, 'id': 'english', 'source': 'english.mp4', 'language': 'en'}
    report = summarize([portuguese, english])
    assert report['by_language']['pt']['reviewed_videos'] == 1
    assert report['by_language']['en']['reviewed_videos'] == 1


def test_experimental_variants_do_not_collapse_when_settings_match(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    reviewed = service.review_job(job['id'], [decision()], expected_revision=0)
    baseline = {**reviewed, 'evaluation': {'cohort': 'synthetic', 'variant': 'baseline'}}
    variant = {**reviewed, 'id': 'variant', 'evaluation': {'cohort': 'synthetic', 'variant': 'signal-boundaries-v1'}}
    report = summarize([baseline, variant])
    assert report['reviewed_videos'] == 1
    assert report['video_configuration_pairs'] == 2
    assert report['paired_comparisons'][0]['paired_videos'] == 1


def test_legacy_unverified_artifact_requires_qc_before_retry(monkeypatch, tmp_path):
    job = record(tmp_path, monkeypatch)
    job['candidates'][0].pop('state')
    store.save(job)
    queued = []
    queue = type('Queue', (), {'lpush': lambda self, key, jid: queued.append(jid)})()
    with pytest.raises(service.Conflict, match='Verify'):
        service.retry_candidate(job['id'], 0, queue=queue)
    assert queued == []
    assert store.load(job['id'])['status'] == 'NEEDS_REVIEW'
