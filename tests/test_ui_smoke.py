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
