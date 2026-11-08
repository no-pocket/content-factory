from test_source_review import jobs
from streamlit.testing.v1 import AppTest
from test_editorial_service_v2 import v2job, review_request
from app import store, service
from app.source_review import list_groups, get_group, select_finals


def session():
    return AppTest.from_string('import streamlit as st\nfrom app.source_review_ui import render_source_review\nrender_source_review(st)',default_timeout=20).run()


def test_review_between_selection_preserves_draft_and_requires_refresh(v2job,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    ui=session();assert not ui.exception
    checkbox=next(c for c in ui.checkbox if c.label=='Selecionar como final')
    checkbox.check().run()
    cid=v2job['candidates'][0]['candidate_id']
    service.review_candidate_v2(v2job['id'],cid,review_request(v2job,decision='APPROVED_WITH_ADJUSTMENTS'))
    ui.run();assert not ui.exception
    assert next(c for c in ui.checkbox if c.label=='Selecionar como final').value
    assert next(b for b in ui.button if b.label.startswith('Salvar seleção')).disabled
    next(b for b in ui.button if b.label=='Atualizar comparação e manter escolhas').click().run()
    next(b for b in ui.button if b.label.startswith('Salvar seleção')).click().run()
    current=get_group(list_groups()[0]['group_id'])
    assert current['candidates'][0]['selected_current']
    assert not current['candidates'][0]['release_ready']
    assert not ui.exception


def test_second_session_cannot_silently_clear_new_selection(v2job,monkeypatch,tmp_path):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    a,b=session(),session()
    next(c for c in a.checkbox if c.label=='Selecionar como final').check().run()
    next(x for x in a.button if x.label.startswith('Salvar seleção')).click().run()
    b.run()
    assert next(x for x in b.button if x.label.startswith('Salvar seleção')).disabled
    assert len(get_group(list_groups()[0]['group_id'])['selection']['selected'])==1
    assert not a.exception and not b.exception

def test_merge_explains_reconciliation_without_choosing_a_winner(jobs):
    from test_source_review import request
    a=jobs('a');b=jobs('b',fingerprint='b'*64)
    ids=[g['group_id'] for g in list_groups()]
    for gid in ids:
        group=get_group(gid);select_finals(gid,request(group))
    b['source_parent_job']=a['id'];store.save(b)
    ui=session()
    assert not ui.exception
    assert any('nenhum final é considerado atual' in w.value for w in ui.warning)
    assert not any(c.value for c in ui.checkbox if c.label=='Selecionar como final')
