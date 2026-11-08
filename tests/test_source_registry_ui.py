from streamlit.testing.v1 import AppTest
from app import store


def test_source_panel_saves_pending_without_clearing_other_drafts(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    ui = AppTest.from_string('import streamlit as st\nfrom app.source_registry_ui import render_source_registry\nst.session_state.setdefault("editorial_draft", "keep me")\nrender_source_registry(st)').run()
    assert not ui.exception
    ui.text_input(key='registry_channel_id').set_value('UC' + 'a' * 22)
    ui.text_input(key='registry_name').set_value('Canal autorizado')
    next(b for b in ui.button if b.label == 'Salvar autorização da fonte').click().run()
    assert not ui.exception
    from app.source_registry import get_source
    record = get_source('UC' + 'a' * 22)
    assert record['status'] == 'pending'
    assert not record['rights_confirmed']
    assert ui.session_state['editorial_draft'] == 'keep me'

def test_stale_source_form_requires_refresh(monkeypatch, tmp_path):
    from app.source_registry import upsert_source, get_source
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    source = {'channel_id': 'UC' + 'b' * 22, 'name': 'Original'}
    upsert_source(source)
    ui = AppTest.from_string('import streamlit as st\nfrom app.source_registry_ui import render_source_registry\nrender_source_registry(st)').run()
    ui.selectbox(key='registry_selection').set_value(source['channel_id']).run()
    upsert_source({**source, 'name': 'Updated elsewhere'}, expected_revision=1)
    ui.text_input(key='registry_' + source['channel_id'] + '_name').set_value('Old draft')
    next(b for b in ui.button if b.label == 'Salvar autorização da fonte').click().run()
    assert get_source(source['channel_id'])['name'] == 'Updated elsewhere'
    assert ui.error

def test_new_form_can_register_two_distinct_sources(monkeypatch, tmp_path):
    from app.source_registry import list_sources
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    ui = AppTest.from_string('import streamlit as st\nfrom app.source_registry_ui import render_source_registry\nrender_source_registry(st)').run()
    for letter in ('a', 'b'):
        ui.text_input(key='registry_channel_id').set_value('UC' + letter * 22)
        ui.text_input(key='registry_name').set_value('Canal ' + letter)
        next(b for b in ui.button if b.label == 'Salvar autorização da fonte').click().run()
    assert len(list_sources()) == 2
    assert not ui.error
