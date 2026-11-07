import copy
import json
from pathlib import Path
import uuid

import pytest


def legacy():
    return json.loads((Path(__file__).parent / 'fixtures/editorial/legacy_reviews.json').read_text())


def test_legacy_qualified_approval_is_unknown():
    from app.editorial_contracts import project_legacy_review
    job = legacy()
    before = copy.deepcopy(job)
    view = project_legacy_review(job, 0)
    assert view['legacy_decision'] == 'APPROVED'
    assert view['comment_raw'] == job['decision_history'][0]['decisions'][0]['reason']
    assert view['normalized_decision'] is None
    assert view['qualification_status'] == 'UNCONFIRMED_LEGACY'
    assert job == before


def test_mixed_job_keeps_candidate_rejection():
    from app.editorial_contracts import project_legacy_review
    assert project_legacy_review(legacy(), 1)['legacy_decision'] == 'REJECTED'


def feedback():
    return {
        'schema_version': '2.0', 'event_id': str(uuid.uuid4()), 'request_id': str(uuid.uuid4()),
        'event_type': 'REVIEW_SUBMITTED', 'job_id': legacy()['id'], 'candidate_id': str(uuid.uuid4()),
        'candidate_version': 1, 'render_revision': 1, 'artifact_id': 'sha256:' + 'a' * 64,
        'editorial_revision': 1, 'supersedes_event_id': None,
        'actor': {'kind': 'human', 'id': 'local-owner', 'channel': 'streamlit'},
        'decision': 'APPROVED_WITH_ADJUSTMENTS', 'rejection_domain': None,
        'comment_raw': 'SYNTHETIC: melhorar final', 'reasons': [], 'dimensions': {},
        'content_grade': None, 'relative_assessment': None, 'edit_requests': [],
        'review_timing': {'active_seconds': None, 'wall_seconds': None},
        'versions': {'brief_id': 'UNKNOWN', 'brief_sha256': 'UNKNOWN', 'component_snapshot_id': 'UNKNOWN'},
        'created_at': '2026-11-07T00:00:00Z',
    }


def test_feedback_bounds_and_id_stability():
    from app.editorial_contracts import candidate_key, validate_feedback_event
    assert candidate_key(legacy()['id'], 0) == str(uuid.uuid5(uuid.NAMESPACE_URL, 'content-factory:' + legacy()['id'] + ':0'))
    assert candidate_key(legacy()['id'], 0) != candidate_key(legacy()['id'], 1)
    for rating in (None, 1, 5):
        event = feedback()
        event['dimensions']['closure'] = rating
        assert validate_feedback_event(event)['dimensions']['closure'] == rating
    for grade in (None, 0, 3):
        event = feedback()
        event['content_grade'] = grade
        assert validate_feedback_event(event)['content_grade'] == grade


@pytest.mark.parametrize('field,value', [
    ('dimensions', {'closure': 0}), ('dimensions', {'closure': 6}),
    ('dimensions', {'closure': True}), ('dimensions', {'closure': float('nan')}),
    ('dimensions', {'invented': 3}), ('content_grade', 4), ('content_grade', True),
    ('candidate_id', '../oops'), ('render_revision', True), ('comment_raw', 'x' * 4001),
    ('actor', {'kind': 'model', 'id': 'qwen', 'channel': 'streamlit'}),
    ('unexpected', 'field'), ('comment_raw', ''),
])
def test_invalid_feedback_rejected(field, value):
    from app.editorial_contracts import validate_feedback_event
    event = feedback()
    event[field] = value
    with pytest.raises(ValueError):
        validate_feedback_event(event)


def test_clean_approval_cannot_hide_major_edits():
    from app.editorial_contracts import validate_feedback_event
    event = feedback()
    event['decision'] = 'APPROVED'
    event['edit_requests'] = [{'edit_id': str(uuid.uuid4()), 'type': 'BOUNDARY_END', 'status': 'OPEN',
                              'severity': 'MAJOR', 'comment': 'SYNTHETIC: final'}]
    with pytest.raises(ValueError):
        validate_feedback_event(event)


def test_pre_history_and_invalidated_reviews_are_not_clean_labels():
    from app.editorial_contracts import project_legacy_review
    job = legacy()
    job['decision_history'] = []
    assert project_legacy_review(job, 0)['legacy_decision'] == 'APPROVED'
    job = legacy()
    job['candidate_review_invalidated_at'] = {'0': 101}
    assert project_legacy_review(job, 0)['normalized_decision'] == 'PENDING'


def test_schema_and_runtime_agree_on_review_rules():
    from jsonschema import Draft202012Validator, FormatChecker
    from app.editorial_contracts import validate_feedback_event
    schema = json.loads((Path(__file__).parent.parent / 'contracts/editorial-feedback-v2.schema.json').read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    event = feedback()
    validator.validate(event)
    assert validate_feedback_event(event) == event
    for field, value in [('decision', 'MODEL_APPROVED'), ('dimensions', {'hook': True}),
                         ('comment_raw', ''), ('actor', {'kind': 'model', 'id': 'x', 'channel': 'api'}),
                         ('reasons', [{'code': 'MADE_UP', 'severity': None, 'confirmed_by': 'human'}])]:
        bad = copy.deepcopy(event)
        bad[field] = value
        assert list(validator.iter_errors(bad))
        with pytest.raises(ValueError):
            validate_feedback_event(bad)


@pytest.mark.parametrize('field,value', [
    ('review_timing', {'active_seconds': float('inf'), 'wall_seconds': None}),
    ('review_timing', {'active_seconds': 20, 'wall_seconds': 10}),
    ('reasons', [{'code': 'ABRUPT_ENDING', 'severity': 'SEVERE', 'confirmed_by': 'human'}]),
    ('created_at', '2026-11-06T12:00:00'),
    ('rejection_domain', 'EDITORIAL'),
    ('versions', {'brief_id': 'v1', 'brief_sha256': 'bad', 'component_snapshot_id': 'UNKNOWN'}),
])
def test_nested_feedback_is_strict(field, value):
    from app.editorial_contracts import validate_feedback_event
    event = feedback()
    event[field] = value
    with pytest.raises(ValueError):
        validate_feedback_event(event)


def test_relative_alternative_optional_render_binding_is_validated():
    from app.editorial_contracts import validate_feedback_event
    event=feedback();cid=event['candidate_id']
    event['relative_assessment']={'comparison_set_id':str(uuid.uuid4()),'preferred_candidate_id':cid,
        'alternatives':[{'candidate_id':cid,'candidate_version':1,'render_revision':1,'artifact_id':event['artifact_id']}],
        'all_options_below_bar':True,'comment':'SYNTHETIC pair','confirmed_by':'human'}
    assert validate_feedback_event(event)['relative_assessment']['alternatives'][0]['artifact_id']==event['artifact_id']
    broken=copy.deepcopy(event);broken['relative_assessment']['alternatives'][0].pop('render_revision')
    with pytest.raises(ValueError):validate_feedback_event(broken)
