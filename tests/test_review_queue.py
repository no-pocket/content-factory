import copy
from pathlib import Path

from app import store, service, dashboard_health, edit_render
from app.artifacts import register_render
from test_editorial_service_v2 import v2job, review_request
from streamlit.testing.v1 import AppTest


def add_candidates(job, count):
    first = job['candidates'][0]
    while len(job['candidates']) < count:
        job['candidates'].append({k: first[k] for k in ('start', 'end', 'state', 'file', 'timeline_file')})
        register_render(job, len(job['candidates']) - 1)
    store.save(job)
    return job


def review(job, index=0, decision='APPROVED'):
    job = store.load(job['id'])
    clip = job['candidates'][index]
    request = review_request(job, decision=decision, expected_artifact_id=clip['artifact_id'], comment_raw='SYNTHETIC review')
    return service.review_candidate_v2(job['id'], clip['candidate_id'], request)


def test_progress_counts_current_candidates_not_events(v2job):
    from app.review_queue import review_progress
    job = add_candidates(v2job, 2)
    for _ in range(3):
        review(job)
    assert review_progress(store.load(job['id'])) == {'total': 2, 'reviewed': 1, 'complete': False}
    review(job, 1, 'APPROVED_WITH_ADJUSTMENTS')
    job = store.load(job['id'])
    assert job['status'] == 'APPROVED' or job['status'] == 'NEEDS_REVIEW'
    assert review_progress(job) == {'total': 2, 'reviewed': 2, 'complete': True}
    register_render(job, 1)
    store.save(job)
    assert review_progress(job) == {'total': 2, 'reviewed': 1, 'complete': False}


def test_empty_processing_job_is_not_a_completed_review():
    from app.review_queue import review_progress
    assert review_progress({'id': 'processing', 'status': 'QUEUED', 'candidates': []}) == {'total': 0, 'reviewed': 0, 'complete': False}


def page(monkeypatch):
    import app
    monkeypatch.setattr(edit_render, 'read_assets', lambda: {})
    monkeypatch.setattr(dashboard_health, 'render_doctor', lambda: None)
    return AppTest.from_file(str(Path(app.__file__).parent / 'ui.py'), default_timeout=20).run()


def test_default_pending_and_completed_jobs_remain_accessible(v2job, monkeypatch):
    review(v2job, decision='APPROVED_WITH_ADJUSTMENTS')
    ui = page(monkeypatch)
    assert not ui.exception
    assert ui.radio(key='editorial_workspace').value == 'Job individual'
    assert ui.selectbox(key='job_filter').value == 'Para revisar'
    assert any('Parabéns' in message.value for message in ui.success)
    ui.selectbox(key='job_filter').set_value('Revisados').run()
    assert ui.selectbox(key='selected_job').value == v2job['id']


def test_last_current_candidate_save_confirms_and_advances(v2job, monkeypatch):
    first = add_candidates(v2job, 2)
    second = copy.deepcopy(first)
    import uuid
    second['id'] = str(uuid.uuid4())
    second['original_name'] = 'SYNTHETIC NEXT JOB'
    second['candidates'] = [{k: first['candidates'][0][k] for k in ('start', 'end', 'state', 'file', 'timeline_file')}]
    folder = store.OUTPUT / second['id']
    folder.mkdir()
    old_file = Path(first['candidates'][0]['file'])
    import shutil
    for source in old_file.parent.iterdir():
        shutil.copyfile(source, folder / source.name)
    second['candidates'][0]['file'] = str(folder / old_file.name)
    second['candidates'][0]['timeline_file'] = str((folder / old_file.name).with_suffix('.timeline.json'))
    register_render(second, 0)
    store.save(second)
    ui = page(monkeypatch)
    ui.selectbox(key='selected_job').set_value(first['id']).run()
    first_comment = next(field for field in ui.text_area if field.label == 'Comentário / motivo')
    first_comment.set_value('SYNTHETIC first')
    next(button for button in ui.button if button.label == 'Aprovar').click().run()
    assert not ui.exception
    assert ui.selectbox(key='selected_job').value == first['id']
    assert not ui.session_state.get('review_queue_transition')
    [field for field in ui.text_area if field.label == 'Comentário / motivo'][1].set_value('SYNTHETIC second')
    [button for button in ui.button if button.label == 'Recusar'][1].click().run()
    assert not ui.exception
    assert ui.selectbox(key='selected_job').value == second['id']
    assert any('2 de 2' in message.value for message in ui.success)
    assert len(store.load(first['id'])['feedback_events']) == 2
    assert not store.load(second['id']).get('feedback_events')


def test_legacy_saved_reviews_are_operationally_complete_not_v2_labels():
    from app.review_queue import review_progress, needs_review
    job = {'id': '58924b9a-dedf-4f56-ab6d-10b25f1240b5', 'status': 'REJECTED',
           'candidates': [{'state': 'VALID'}, {'state': 'WARNING'}], 'approved': []}
    assert review_progress(job) == {'total': 2, 'reviewed': 2, 'complete': True}
    assert not needs_review(job)
    assert all(row['normalized_decision'] is None for row in service.get_editorial_view(job)['candidates'])
    job['status'] = 'NEEDS_REVIEW'
    assert needs_review(job)


def test_render_change_between_completion_and_redirect_cancels_advance(v2job):
    from app.review_queue import review_progress, completion_identity, apply_completion
    review(v2job)
    completed = store.load(v2job['id'])
    token = {'job_id': completed['id'], 'identity': completion_identity(completed)}
    register_render(completed, 0)
    store.save(completed)
    state = {'selected_job': completed['id'], 'review_queue_transition': token}
    assert not apply_completion(state, [completed])
    assert state['selected_job'] == completed['id']
    assert not state.get('review_queue_confirmation')
    assert not review_progress(completed)['complete']


def test_last_job_completion_confirms_actual_count_and_empty_queue(v2job, monkeypatch):
    ui = page(monkeypatch)
    next(button for button in ui.button if button.label == 'Aprovar').click().run()
    assert not ui.exception
    assert any('1 de 1' in message.value for message in ui.success)
    assert any('Parabéns' in message.value for message in ui.success)
    assert not [field for field in ui.text_area if field.label == 'Comentário / motivo']
    ui.selectbox(key='job_filter').set_value('Revisados').run()
    assert ui.selectbox(key='selected_job').value == v2job['id']


def test_old_completed_job_filter_migrates_without_hiding_saved_review(v2job, monkeypatch):
    import app
    review(v2job)
    monkeypatch.setattr(edit_render, 'read_assets', lambda: {})
    monkeypatch.setattr(dashboard_health, 'render_doctor', lambda: None)
    ui = AppTest.from_file(str(Path(app.__file__).parent / 'ui.py'), default_timeout=20)
    ui.session_state['job_filter'] = 'Aprovados'
    ui.session_state['selected_job'] = v2job['id']
    ui.run()
    assert not ui.exception
    assert ui.selectbox(key='job_filter').value == 'Revisados'
    assert ui.selectbox(key='selected_job').value == v2job['id']
