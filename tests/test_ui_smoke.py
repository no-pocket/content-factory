from pathlib import Path

import app
from app import store, dashboard_health, edit_render
from app.job_settings import DEFAULTS
from app.version import VERSION
from streamlit.testing.v1 import AppTest
from test_editorial_service_v2 import v2job


def test_streamlit_form_exposes_per_job_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'all_jobs', lambda: [])
    monkeypatch.setattr(edit_render, 'read_assets', lambda: {})
    monkeypatch.setattr(dashboard_health, 'render_doctor', lambda: None)
    test = AppTest.from_file(str(Path(app.__file__).parent / 'ui.py')).run(timeout=20)
    assert not test.exception
    assert len(test.get('number_input')) + len(test.get('selectbox')) + len([t for t in test.text_input if t.label.startswith(('Região importante','Intervalos de página/tweet','Dataset de exemplos'))]) == len(DEFAULTS)
    assert any(VERSION in item.value for item in test.caption)


def test_gpu_job_status_names_actual_backend(monkeypatch):
    messages = []
    monkeypatch.setattr(dashboard_health.st, 'success', messages.append)
    dashboard_health.render_job_ai({'ranker_used': 'kepler_gpu', 'ai_activity': {}})
    assert messages and 'GPU' in messages[0]


def test_selected_job_survives_status_change(monkeypatch):
    jobs = [{'id': 'a', 'original_name': 'a.mp4', 'creator': 'test', 'license_note': 'grant',
             'status': 'QUEUED', 'candidates': []},
            {'id': 'b', 'original_name': 'b.mp4', 'creator': 'test', 'license_note': 'grant',
             'status': 'QUEUED', 'candidates': []}]
    monkeypatch.setattr(store, 'all_jobs', lambda: jobs)
    monkeypatch.setattr(store, 'load', lambda jid: next(j for j in jobs if j['id'] == jid))
    monkeypatch.setattr(edit_render, 'read_assets', lambda: {})
    monkeypatch.setattr(dashboard_health, 'render_doctor', lambda: None)
    test = AppTest.from_file(str(Path(app.__file__).parent / 'ui.py')).run(timeout=20)
    test.radio(key='editorial_workspace').set_value('Job individual').run()
    test.selectbox(key='selected_job').set_value('a').run()
    jobs[0]['status'] = 'FAILED'
    test.run()
    assert test.selectbox(key='selected_job').value == 'a'
    assert not test.exception


def test_v2_adjustment_and_rejection_persist_without_ratings(v2job, monkeypatch):
    from app import service
    monkeypatch.setattr(store, 'all_jobs', lambda: [store.load(v2job['id'])])
    monkeypatch.setattr(edit_render, 'read_assets', lambda: {})
    monkeypatch.setattr(dashboard_health, 'render_doctor', lambda: None)
    test = AppTest.from_file(str(Path(app.__file__).parent / 'ui.py')).run(timeout=20)
    assert not test.exception
    test.radio(key='editorial_workspace').set_value('Job individual').run()
    comment = next(t for t in test.text_area if t.label == 'Comentário / motivo')
    comment.set_value('SYNTHETIC: bom, mas melhorar o final').run()
    next(b for b in test.button if b.label == 'Aprovar com ajustes').click().run()
    assert not test.exception
    job = store.load(v2job['id'])
    assert job['feedback_events'][-1]['decision'] == 'APPROVED_WITH_ADJUSTMENTS'
    assert all(value is None for value in job['feedback_events'][-1]['dimensions'].values())
    assert job['approved'] == []
    next(t for t in test.text_area if t.label == 'Comentário / motivo').set_value('SYNTHETIC: recusa editorial').run()
    next(b for b in test.button if b.label == 'Recusar').click().run()
    assert not test.exception
    assert store.load(v2job['id'])['feedback_events'][-1]['decision'] == 'REJECTED'
    assert len(store.load(v2job['id'])['feedback_events']) == 2
    test.selectbox(key='candidate_filter').set_value('REJECTED').run()
    assert len([h for h in test.get('header') if h.value.startswith('Candidato')]) <= 1
    assert len([t for t in test.text_area if t.label == 'Comentário / motivo']) == 1

def test_existing_review_session_keeps_individual_workspace_and_comment_draft(v2job,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    monkeypatch.setattr(edit_render,'read_assets',lambda: {})
    monkeypatch.setattr(dashboard_health,'render_doctor',lambda: None)
    test=AppTest.from_file(str(Path(app.__file__).parent/'ui.py'))
    clip=v2job['candidates'][0]
    draft_key=f"v2_{v2job['id']}_{clip['candidate_id']}_{clip['artifact_id']}_comment"
    test.session_state['selected_job']=v2job['id']
    test.session_state[draft_key]='SYNTHETIC: rascunho aberto antes da atualização'
    test.run(timeout=20)
    assert not test.exception
    assert test.radio(key='editorial_workspace').value=='Job individual'
    assert test.selectbox(key='selected_job').value==v2job['id']
    assert test.text_area(key=draft_key).value=='SYNTHETIC: rascunho aberto antes da atualização'
