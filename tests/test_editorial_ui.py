from app import service
from app.editorial_contracts import candidate_key
from test_editorial_service_v2 import v2job


def mixed_legacy():
    return {'id': '58924b9a-dedf-4f56-ab6d-10b25f1240b5', 'status': 'APPROVED',
            'candidates': [{}, {}], 'approved': [0], 'decision_history': [
                {'at': 100, 'decisions': [
                    {'candidate': 0, 'decision': 'APPROVED', 'reason': 'SYNTHETIC: final ruim'},
                    {'candidate': 1, 'decision': 'REJECTED', 'reason': 'SYNTHETIC: irrelevante'}]}]}


def test_filter_finds_rejected_inside_approved_job():
    from app.editorial_ui import filter_candidates
    rows = service.get_editorial_view(mixed_legacy())['candidates']
    filtered = filter_candidates(rows, {'decision': 'REJECTED'})
    assert [r['candidate_id'] for r in filtered] == [candidate_key(mixed_legacy()['id'], 1)]
    assert filtered[0]['legacy_decision'] == 'REJECTED'


def test_conditional_is_not_clean_approval():
    from app.editorial import summarize_v2
    from app.editorial_ui import filter_candidates
    rows = [{'normalized_decision': 'APPROVED', 'legacy_decision': None},
            {'normalized_decision': 'APPROVED_WITH_ADJUSTMENTS', 'legacy_decision': None}]
    assert len(filter_candidates(rows, {'decision': 'APPROVED'})) == 1
    report = summarize_v2([mixed_legacy()])
    assert report['clean_approved'] == 0
    assert report['unconfirmed_legacy'] == 2
    assert report['acceptance_at_3_clean'] is None
    # A v2 adjusted result can coexist with a legacy job-status projection.
    assert filter_candidates([{'normalized_decision': 'APPROVED_WITH_ADJUSTMENTS',
                               'legacy_decision': 'REJECTED'}], {'decision': 'REJECTED'}) == []


def test_unreviewed_slot_keeps_metric_coverage_explicit():
    from app.editorial import summarize_v2
    pending = {'id': '58924b9a-dedf-4f56-ab6d-10b25f1240b5', 'status': 'NEEDS_REVIEW',
               'editorial_protocol': 2, 'candidates': [{}, {}]}
    report = summarize_v2([pending])
    assert report['queries_total'] == 1
    assert report['queries_eligible'] == 0
    assert report['review_coverage'] == 0
    assert report['acceptance_at_3_clean'] is None


def test_fully_reviewed_two_candidate_pool_uses_three_slots(v2job):
    from test_editorial_service_v2 import review_request
    from app.editorial import summarize_v2
    from app import store
    job = v2job
    # One actual candidate: missing two top-three slots contribute zero.
    service.review_candidate_v2(job['id'], job['candidates'][0]['candidate_id'], review_request(job))
    report = summarize_v2([store.load(job['id'])])
    assert report['acceptance_at_3_clean'] == 1/3
    assert report['review_coverage'] == 1
