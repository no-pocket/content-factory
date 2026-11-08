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


def ui_test_session(job):
    from streamlit.testing.v1 import AppTest
    code=f'''from app import store,service
from app.editorial_ui import render_v2_review
job=store.load({job['id']!r})
render_v2_review(__import__('streamlit'),job,0,service.get_editorial_view(job)['candidates'][0])
'''
    return AppTest.from_string(code,default_timeout=15).run()


def test_two_ui_sessions_keep_original_revision_and_preserve_stale_draft(v2job):
    from app import store
    a,b=ui_test_session(v2job),ui_test_session(v2job)
    a.text_area[0].set_value('Session A approved');a.button[0].click().run()
    assert not a.exception
    b.text_area[0].set_value('Session B old draft');b.button[0].click().run()
    assert not b.exception
    assert len(store.load(v2job['id'])['feedback_events'])==1
    assert b.error and b.text_area[0].value=='Session B old draft'
    next(button for button in b.button if button.label.startswith('Recarregar avaliação')).click().run()
    assert b.text_area[0].value=='Session A approved'
    next(button for button in b.button if button.label=='Aprovar').click().run()
    assert len(store.load(v2job['id'])['feedback_events'])==2


def test_reviewing_one_candidate_does_not_stale_other_candidate_draft(v2job):
    from app import store
    from app.artifacts import register_render
    from streamlit.testing.v1 import AppTest
    first=v2job['candidates'][0]
    v2job['candidates'].append({key:first[key] for key in ('start','end','state','file','timeline_file')})
    register_render(v2job,1);store.save(v2job)
    code=f'''from app import store,service
from app.editorial_ui import render_v2_review
import streamlit as st
job=store.load({v2job['id']!r})
for i,row in enumerate(service.get_editorial_view(job)['candidates']):
    render_v2_review(st,job,i,row)
'''
    page=AppTest.from_string(code,default_timeout=20).run()
    page.text_area[2].set_value('Second candidate draft')
    next(b for b in page.button if b.label=='Aprovar').click().run()
    assert not page.exception
    [b for b in page.button if b.label=='Recusar'][1].click().run()
    assert not page.exception and not page.error
    events=store.load(v2job['id'])['feedback_events']
    assert len(events)==2 and events[-1]['comment_raw']=='Second candidate draft'


def test_explicit_refresh_can_keep_stale_comment_without_submitting(v2job):
    from app import store
    a,b=ui_test_session(v2job),ui_test_session(v2job)
    next(x for x in a.button if x.label=='Aprovar').click().run()
    b.text_area[0].set_value('Preserve this draft')
    next(x for x in b.button if x.label=='Aprovar').click().run()
    assert b.error
    next(x for x in b.button if x.label=='Atualizar revisão e manter meu rascunho').click().run()
    assert b.text_area[0].value=='Preserve this draft'
    assert len(store.load(v2job['id'])['feedback_events'])==1
    next(x for x in b.button if x.label=='Aprovar').click().run()
    assert not b.error and store.load(v2job['id'])['feedback_events'][-1]['comment_raw']=='Preserve this draft'


def test_adding_minor_edit_preserves_existing_major_and_blocks_clean_approval(v2job):
    import uuid
    from app import store
    from test_editorial_service_v2 import review_request
    edit={'edit_id':str(uuid.uuid4()),'type':'BOUNDARY_END','status':'OPEN','severity':'MAJOR','comment':'SYNTHETIC major ending'}
    request=review_request(v2job,decision='APPROVED_WITH_ADJUSTMENTS',edit_requests=[edit])
    service.review_candidate_v2(v2job['id'],v2job['candidates'][0]['candidate_id'],request)
    view=ui_test_session(v2job)
    view.text_area[1].set_value('SYNTHETIC minor title')
    view.selectbox[0].set_value('MINOR')
    view.button[0].click().run()
    assert not view.exception
    assert view.error
    latest=store.load(v2job['id'])['feedback_events'][-1]
    assert latest['edit_requests']==[edit] and latest['decision']=='APPROVED_WITH_ADJUSTMENTS'
    next(button for button in view.button if button.label=='Aprovar com ajustes').click().run()
    latest=store.load(v2job['id'])['feedback_events'][-1]
    assert latest['edit_requests'][0]==edit and len(latest['edit_requests'])==2
    assert view.text_area[1].value==''  # no duplicate request on the next submission
    next(select for select in view.multiselect if select.label=='Pedidos resolvidos nesta revisão').set_value([edit['edit_id']])
    next(button for button in view.button if button.label=='Aprovar').click().run()
    assert not view.error and not view.exception
    latest=store.load(v2job['id'])['feedback_events'][-1]
    assert latest['decision']=='APPROVED' and latest['edit_requests'][0]['status']=='RESOLVED'
