from datetime import date, time

import pytest

from app.publication_calendar import local_timestamp, month_grid


def test_calendar_has_full_weeks_and_correct_dates():
    grid = month_grid(2026, 11)
    assert all(len(week) == 7 for week in grid)
    assert sum(day != 0 for week in grid for day in week) == 30
    assert grid[0][-1] == 1


def test_local_time_converts_to_utc_and_rejects_nonexistent_time():
    assert local_timestamp(date(2026, 11, 10), time(12), 'America/Sao_Paulo') == 1794322800
    with pytest.raises(ValueError):
        local_timestamp(date(2026, 3, 8), time(2, 30), 'America/New_York')


def test_caption_edit_survives_destination_switch(v2job, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from app import store, publication_schedule
    from test_publishing import approved
    monkeypatch.setattr(publication_schedule, 'ROOT', tmp_path/'agenda')
    job=approved(v2job)
    job['candidates'][0]['social_captions']={
        'instagram':{'text':'Sugestão Instagram', 'origin':'fallback', 'reason':None},
        'facebook':{'text':'Sugestão Facebook', 'origin':'fallback', 'reason':None}}
    store.save(job)
    test=AppTest.from_string('import streamlit as st\nfrom app.store import all_jobs\nfrom app.publication_calendar import render\nrender(st, all_jobs())').run(timeout=20)
    test.multiselect[0].set_value(['instagram']).run(timeout=20)
    assert test.text_area[0].value == 'Sugestão Instagram'
    test.text_area[0].set_value('Minha legenda').run(timeout=20)
    test.multiselect[0].set_value(['facebook']).run(timeout=20)
    test.multiselect[0].set_value(['instagram']).run(timeout=20)
    assert not test.exception
    assert test.text_area[0].value == 'Minha legenda'


def test_each_destination_uses_its_own_caption_when_scheduled(v2job, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from app import store, publication_schedule
    from test_publishing import approved
    monkeypatch.setattr(publication_schedule, 'ROOT', tmp_path/'agenda')
    job=approved(v2job)
    job['candidates'][0]['social_captions']={
        'instagram':{'text':'Legenda Instagram', 'origin':'fallback', 'reason':None},
        'facebook':{'text':'Legenda Facebook', 'origin':'fallback', 'reason':None}}
    store.save(job)
    captured=[]
    monkeypatch.setattr(publication_schedule, 'schedule', lambda *a, **kw: captured.append((a[2],kw['caption'])))
    test=AppTest.from_string('import streamlit as st\nfrom app.store import all_jobs\nfrom app.publication_calendar import render\nrender(st, all_jobs())').run(timeout=20)
    test.multiselect[0].set_value(['instagram','facebook']).run(timeout=20)
    test.text_input[0].set_value('123')
    test.text_input[1].set_value('456')
    test.text_input[2].set_value('Título')
    next(b for b in test.button if b.label=='Confirmar publicação').click().run(timeout=20)
    assert not test.exception
    assert captured==[('instagram','Legenda Instagram'),('facebook','Legenda Facebook')]


def test_caption_edit_survives_candidate_switch(v2job, tmp_path, monkeypatch):
    import copy
    from streamlit.testing.v1 import AppTest
    from app import service, store, publication_schedule
    from app.artifacts import register_render
    from test_publishing import approved
    from test_editorial_service_v2 import review_request
    monkeypatch.setattr(publication_schedule, 'ROOT', tmp_path/'agenda')
    job=approved(v2job)
    second=copy.deepcopy(job['candidates'][0])
    for key in ('candidate_id','artifact_id','artifact_manifest','render_revision','candidate_version'):
        second.pop(key, None)
    root=store.OUTPUT/job['id']
    master=root/'candidate_2.mp4'
    master.write_bytes(b'another synthetic master')
    master.with_suffix('.preview.webm').write_bytes(b'preview')
    master.with_suffix('.timeline.json').write_text('{}')
    second.update(start=20,end=30,file=str(master),timeline_file=str(master.with_suffix('.timeline.json')))
    job['candidates'].append(second)
    register_render(job,1)
    store.save(job)
    request=review_request(job,expected_artifact_id=job['candidates'][1]['artifact_id'])
    service.review_candidate_v2(job['id'],job['candidates'][1]['candidate_id'],request)
    test=AppTest.from_string('import streamlit as st\nfrom app.store import all_jobs\nfrom app.publication_calendar import render\nrender(st, all_jobs())').run(timeout=20)
    test.multiselect[0].set_value(['instagram']).run(timeout=20)
    test.text_area[0].set_value('Minha edição no primeiro').run(timeout=20)
    test.selectbox[0].set_value(1).run(timeout=20)
    test.selectbox[0].set_value(0).run(timeout=20)
    assert not test.exception
    assert test.text_area[0].value=='Minha edição no primeiro'


from test_editorial_service_v2 import v2job
