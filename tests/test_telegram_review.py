import time
from pathlib import Path
import pytest

from app import service, store
from test_editorial_service_v2 import v2job


@pytest.fixture
def telegram(v2job,tmp_path,monkeypatch):
    from app import telegram_review as tg
    config={'mode':'live','allowed_destinations':['synthetic-chat'],'allowed_actors':['synthetic-owner'],
            'callback_ttl_seconds':3600,'max_attempts':3,'max_video_bytes':50_000_000}
    monkeypatch.setattr(tg,'ROOT',tmp_path/'telegram')
    monkeypatch.setattr(tg,'load_config',lambda:config)
    return tg,config


def queued(v2job,telegram):
    tg,config=telegram
    return tg.queue_review_delivery(v2job['id'],v2job['candidates'][0]['candidate_id'],destination_id='synthetic-chat')


def callback(item,action='APPROVED',comment='SYNTHETIC review'):
    return {'data':next(token for token,payload in item['callbacks'].items() if payload['decision']==action),
            'actor_id':'synthetic-owner','destination_id':'synthetic-chat','comment_raw':comment}


def test_old_render_callback_is_rejected(v2job,telegram):
    tg,config=telegram
    item=queued(v2job,telegram)
    from app.artifacts import register_render
    job=store.load(v2job['id']);register_render(job,0);store.save(job)
    with pytest.raises(service.Conflict):tg.handle_review_callback(callback(item),config)
    assert store.load(job['id']).get('feedback_events',[])==[]


def test_unauthorized_actor_cannot_review(v2job,telegram):
    tg,config=telegram;item=queued(v2job,telegram)
    with pytest.raises(PermissionError):
        tg.handle_review_callback({**callback(item),'actor_id':'not-allowed'},config)
    assert store.load(v2job['id']).get('feedback_events',[])==[]


def test_redelivery_does_not_duplicate_event(v2job,telegram):
    tg,config=telegram;first=queued(v2job,telegram)
    assert queued(v2job,telegram)['delivery_id']==first['delivery_id']
    result=tg.handle_review_callback(callback(first),config)
    assert tg.handle_review_callback(callback(first),config)==result
    events=store.load(v2job['id'])['feedback_events']
    assert len(events)==1 and events[0]['actor']['id']=='telegram:synthetic-owner'
    assert service.get_editorial_view(store.load(v2job['id']))['candidates'][0]['normalized_decision']=='APPROVED'


def test_adjustment_requires_comment(v2job,telegram):
    tg,config=telegram;item=queued(v2job,telegram)
    result=tg.handle_review_callback(callback(item,'APPROVED_WITH_ADJUSTMENTS',''),config)
    assert result['status']=='COMMENT_REQUIRED'
    assert store.load(v2job['id']).get('feedback_events',[])==[]
    result=tg.handle_review_callback(callback(item,'APPROVED_WITH_ADJUSTMENTS','SYNTHETIC: melhorar final'),config)
    assert result['event']['decision']=='APPROVED_WITH_ADJUSTMENTS'


def test_expired_callback_never_reviews(v2job,telegram,monkeypatch):
    tg,config=telegram;item=queued(v2job,telegram)
    monkeypatch.setattr(tg.time,'time',lambda:item['expires_at']+1)
    with pytest.raises(service.Conflict,match='expired'):tg.handle_review_callback(callback(item),config)


def test_dry_run_delivery_does_not_call_transport(v2job,telegram):
    tg,config=telegram;item=queued(v2job,telegram)
    config={**config,'mode':'dry-run'}
    class Forbidden:
        def send_review_card(self,*args):pytest.fail('Dry-run attempted delivery')
    result=tg.deliver_review(item['delivery_id'],config,Forbidden())
    assert result['status']=='DRY_RUN' and result['state']=='PENDING'


def test_dry_run_callback_never_writes_human_feedback(v2job,telegram):
    tg,config=telegram;item=queued(v2job,telegram)
    result=tg.handle_review_callback(callback(item),{**config,'mode':'dry-run'})
    assert result['status']=='DRY_RUN'
    assert store.load(v2job['id']).get('feedback_events',[])==[]


def test_failed_transport_retries_bounded_and_large_media_is_explicit(v2job,telegram):
    tg,config=telegram;item=queued(v2job,telegram)
    config={**config,'mode':'live'}
    class Broken:
        def send_review_card(self,*args):raise TimeoutError('synthetic timeout; never log this text')
    for _ in range(3):result=tg.deliver_review(item['delivery_id'],config,Broken())
    assert result['state']=='FAILED' and result['attempts']==3
    assert 'timeout' not in result.get('last_error','').casefold() or result['last_error']=='TimeoutError'
    assert tg.deliver_review(item['delivery_id'],config,Broken())['attempts']==3
    # Size is checked before transmission; original master is never reduced.
    config={**config,'max_video_bytes':1}
    item['card']['editorial_revision']=99
    with pytest.raises(ValueError,match='size'):
        tg.build_review_card(v2job,v2job['candidates'][0]['candidate_id'],max_video_bytes=1)


def test_polling_restart_collects_comment_and_deduplicates_update(v2job,telegram):
    tg,config=telegram;item=queued(v2job,telegram);config={**config,'mode':'live'}
    token=callback(item,'REJECTED')['data']
    class FakeTransport:
        updates=[]
        def send_review_card(self,*args):return {'message_id':77}
        def get_updates(self,**kwargs):return self.updates
        def answer_callback_query(self,*args):return True
    transport=FakeTransport()
    tg.deliver_review(item['delivery_id'],config,transport)
    transport.updates=[{'update_id':1,'callback_query':{'id':'query','from':{'id':'synthetic-owner'},'data':token,
        'message':{'message_id':77,'chat':{'id':'synthetic-chat','type':'private'}}}}]
    assert tg.poll_once(config,transport)['offset']==2
    assert not store.load(v2job['id']).get('feedback_events')
    transport.updates=[{'update_id':2,'message':{'from':{'id':'synthetic-owner'},'chat':{'id':'synthetic-chat','type':'private'},
        'reply_to_message':{'message_id':77},'text':'SYNTHETIC: recusa com comentário literal $(noop)'}}]
    assert tg.poll_once(config,transport)['offset']==3
    assert tg.poll_once(config,transport)['offset']==3
    job=store.load(v2job['id'])
    assert len(job['feedback_events'])==1
    assert job['feedback_events'][0]['comment_raw']=='SYNTHETIC: recusa com comentário literal $(noop)'
