from pathlib import Path

import app
from app import store, dashboard_health, edit_render
from app.job_settings import DEFAULTS
from app.version import VERSION
from streamlit.testing.v1 import AppTest


def test_streamlit_form_exposes_per_job_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'all_jobs', lambda: [])
    monkeypatch.setattr(edit_render, 'read_assets', lambda: {})
    monkeypatch.setattr(dashboard_health, 'render_doctor', lambda: None)
    test = AppTest.from_file(str(Path(app.__file__).parent / 'ui.py')).run(timeout=20)
    assert not test.exception
    assert len(test.get('number_input')) + len(test.get('selectbox')) == len(DEFAULTS)
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
    test.selectbox(key='selected_job').set_value('a').run()
    jobs[0]['status'] = 'FAILED'
    test.run()
    assert test.selectbox(key='selected_job').value == 'a'
    assert not test.exception
