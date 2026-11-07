"""Synthetic editorial actions, not evaluations of real clips."""
from app import service, store
from app.editorial import summarize


def fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    monkeypatch.setattr(service, 'verify_reviewable', lambda *a: True)
    job = store.new_job(tmp_path/'source.mp4', 'SYNTHETIC.mp4', 'synthetic', 'synthetic grant')
    job.update(status='NEEDS_REVIEW', candidates=[{'start': 0, 'end': 20, 'state': 'VALID'},
                                                  {'start': 25, 'end': 45, 'state': 'VALID'}])
    store.save(job)
    return job


def test_reject_job_does_not_require_qc_or_invent_ratings(monkeypatch, tmp_path):
    job = fixture(monkeypatch, tmp_path)
    job['candidates'][0]['state'] = 'FAILED'
    job.update(status='APPROVED', approved=[1])
    store.save(job)
    def forbidden(*a):
        raise AssertionError('Rejection must not require approval QC')
    monkeypatch.setattr(service, 'verify_reviewable', forbidden)
    result = service.reject_job(job['id'], 'Synthetic user rejection with comments')
    assert result['status'] == 'REJECTED' and result['approved'] == []
    assert result['legacy_decision']['approved'] == [1]
    assert result['decision_history'][-1]['decisions'][0]['hook'] is None
    assert summarize([result])['approved_per_video'] == 0


def test_individual_rejection_comments_and_partial_review(monkeypatch, tmp_path):
    job = fixture(monkeypatch, tmp_path)
    first = service.review_candidate(job['id'], 0, 'REJECTED', 'Synthetic comment', expected_revision=0)
    assert first['status'] == 'NEEDS_REVIEW'
    assert first['decision_history'][-1]['review_complete'] is False
    assert summarize([first])['reviewed_videos'] == 0
    second = service.review_candidate(job['id'], 1, 'APPROVED', 'Synthetic approval', expected_revision=1,
                                      origin='explicit_user_message')
    assert second['approved'] == [1]
    assert len(second['decision_history']) == 2
    assert second['decision_history'][-1]['review_complete'] is True
    assert second['decision_history'][-1]['origin'] == 'explicit_user_message'
    assert summarize([second])['approved_per_video'] == 1


def test_review_after_retry_preserves_unchanged_sibling(monkeypatch, tmp_path):
    job=fixture(monkeypatch,tmp_path)
    service.review_candidate(job['id'],0,'APPROVED','Synthetic good sibling',expected_revision=0)
    current=service.review_candidate(job['id'],1,'REJECTED','Synthetic failed sibling',expected_revision=1)
    service.invalidate_approvals(current,{1}); store.save(current)
    updated=service.review_candidate(job['id'],1,'REJECTED','Synthetic retry still bad',expected_revision=2)
    assert updated['approved']==[0]
    assert updated['decision_history'][-1]['review_complete'] is True
    assert updated['decision_history'][-1]['decisions'][0]['reason']=='Synthetic good sibling'


def test_empty_rejected_jobs_have_undefined_rework_delta_not_crash(monkeypatch,tmp_path):
    job=fixture(monkeypatch,tmp_path);job['candidates']=[];store.save(job)
    one=service.reject_job(job['id'],'Synthetic administrative rejection')
    two={**one,'id':'variant','settings':{**one['settings'],'llm_model':'qwen2.5:1.5b'}}
    report=summarize([one,two])
    assert report['paired_comparisons'][0]['rows'][0]['rework_delta'] is None
