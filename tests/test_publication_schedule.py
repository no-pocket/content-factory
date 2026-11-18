import pytest

from app import service, store
from test_publishing import approved
from test_editorial_service_v2 import v2job


def test_scheduling_requires_current_approval_and_freezes_artifact(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    cid = v2job['candidates'][0]['candidate_id']
    with pytest.raises(service.Conflict):
        agenda.schedule(v2job['id'], cid, 'instagram', title='Teste', caption='', scheduled_at=2000000000, page_id='123', instagram_id='456')
    job = approved(v2job)
    result = agenda.schedule(job['id'], cid, 'instagram', title='Teste', caption='', scheduled_at=2000000000, page_id='123', instagram_id='456')
    assert result['state'] == 'SCHEDULED'
    assert result['draft']['artifact_id'] == job['candidates'][0]['artifact_id']
    assert agenda.list_items()[0]['id'] == result['id']


def test_cancelled_schedule_is_not_due(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'facebook', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='456')
    agenda.cancel(item['id'])
    assert agenda.due_items(now=2) == []


def test_execution_refuses_changed_master(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'instagram', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='456')
    from pathlib import Path
    Path(job['candidates'][0]['file']).write_bytes(b'changed')
    calls = []
    result = agenda.execute(item['id'], lambda *args: calls.append(args), now=2)
    assert result['state'] == 'BLOCKED'
    assert not calls


def test_ambiguous_execution_never_retries(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'facebook', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='456')
    def fail(*args):
        raise TimeoutError('uncertain outcome')
    assert agenda.execute(item['id'], fail, now=2)['state'] == 'UNCERTAIN'
    assert agenda.due_items(now=2) == []


def test_uncertain_failure_records_safe_reason_without_exception_text(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job=approved(v2job)
    item=agenda.schedule(job['id'],job['candidates'][0]['candidate_id'],'instagram',title='Teste',caption='',scheduled_at=1,page_id='123',instagram_id='456')
    def fail(draft,job,destination,progress):
        progress('SENDING','987')
        raise ConnectionResetError('PRIVATE_SECRET')
    result=agenda.execute(item['id'],fail,now=2)
    assert result['state']=='UNCERTAIN' and result['failure_detail']=='connection_reset'
    assert 'PRIVATE_SECRET' not in str(result)
    retried=agenda.retry(item['id'],confirmed_not_published=True)
    assert retried['attempt_history'][-1]['failure_detail']=='connection_reset'


def test_failure_details_allow_only_safe_http_codes():
    from app import publication_schedule as agenda
    from app.meta_http import MetaHTTPError
    assert agenda._failure_detail(MetaHTTPError('Meta request failed (HTTP 503)'))=='meta_http_503'
    assert agenda._failure_detail(MetaHTTPError('private token'))=='meta_response_error'


def test_destination_is_bound_when_scheduled(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'instagram', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='456')
    assert item['destination'] == {'page_id': '123', 'instagram_id': '456'}
    with pytest.raises(ValueError):
        agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'instagram', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='bad')


def test_remote_progress_survives_an_uncertain_publication(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'instagram', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='456')
    def send(draft, job, destination, progress):
        progress('PROCESSING', '987')
        raise TimeoutError('response lost')
    result = agenda.execute(item['id'], send, now=2)
    assert result['state'] == 'UNCERTAIN'
    assert result['remote_container_id'] == '987'
    assert agenda.list_items()[0]['remote_container_id'] == '987'


def test_duplicate_scheduling_of_the_same_publication_is_idempotent(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    args = (job['id'], job['candidates'][0]['candidate_id'], 'facebook')
    kwargs = dict(title='Teste', caption='Texto', scheduled_at=1234, page_id='123')
    first = agenda.schedule(*args, **kwargs)
    assert agenda.schedule(*args, **kwargs)['id'] == first['id']
    assert len(agenda.list_items()) == 1


def test_pending_time_can_be_changed_but_cancelled_item_cannot(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'facebook', title='Teste', caption='', scheduled_at=1234, page_id='123')
    assert agenda.reschedule(item['id'], 2345, 'America/Sao_Paulo')['scheduled_at'] == 2345
    agenda.cancel(item['id'])
    with pytest.raises(ValueError):
        agenda.reschedule(item['id'], 3456, 'America/Sao_Paulo')


def test_preflight_failure_is_blocked_not_ambiguous(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'facebook', title='Teste', caption='', scheduled_at=1, page_id='123')
    def fail(*args):
        raise agenda.PreflightError('Credenciais indisponíveis')
    result = agenda.execute(item['id'], fail, now=2)
    assert result['state'] == 'BLOCKED'
    assert 'Credenciais' in result['error']


def test_future_publication_waits_until_due_and_then_confirms(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'instagram', title='Teste', caption='Teste', scheduled_at=100, page_id='123', instagram_id='456')
    assert agenda.due_items(now=99) == []
    with pytest.raises(ValueError):
        agenda.execute(item['id'], lambda *_: None, now=99)
    def send(draft, current_job, destination, progress):
        progress('PROCESSING', '789')
        return {'confirmed': True, 'remote_id': '987', 'permalink': 'https://www.instagram.com/reel/test/'}
    result = agenda.execute(item['id'], send, now=100)
    assert result['state'] == 'PUBLISHED' and result['remote_id'] == '987'
    assert agenda.due_items(now=101) == []

def test_uncertain_retry_requires_confirmation_and_preserves_history(v2job, tmp_path, monkeypatch):
    from app import publication_schedule as agenda
    monkeypatch.setattr(agenda, 'ROOT', tmp_path)
    job = approved(v2job)
    item = agenda.schedule(job['id'], job['candidates'][0]['candidate_id'], 'instagram', title='Teste', caption='', scheduled_at=1, page_id='123', instagram_id='456')
    def fail(draft, job, destination, progress):
        progress('PROCESSING', '987')
        raise TimeoutError('private details')
    result = agenda.execute(item['id'], fail, now=2)
    assert result['failure_stage'] == 'PROCESSING'
    assert result['failure_kind'] == 'timeout'
    with pytest.raises(ValueError):
        agenda.retry(item['id'], confirmed_not_published=False)
    retried = agenda.retry(item['id'], confirmed_not_published=True)
    assert retried['state'] == 'SCHEDULED'
    assert retried['attempt_history'][-1]['remote_container_id'] == '987'
    with pytest.raises(ValueError):
        agenda.retry(item['id'], confirmed_not_published=True)
