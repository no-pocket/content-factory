"""Private review outbox and callbacks; external transport is opt-in and injected."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import secrets
import time
import uuid

from . import service, store
from .artifacts import digest

ROOT = store.ROOT / 'telegram'
ACTIONS = {'APPROVED':'Aprovar','APPROVED_WITH_ADJUSTMENTS':'Aprovar com ajustes','REJECTED':'Recusar'}
TOKEN = re.compile(r'([0-9a-f]{32}):([A-Za-z0-9_-]{16})')


def load_config() -> dict:
    def items(name):return [v.strip() for v in os.getenv(name,'').split(',') if v.strip()]
    return {'mode':os.getenv('CONTENT_FACTORY_TELEGRAM_MODE','dry-run'),
            'allowed_destinations':items('CONTENT_FACTORY_TELEGRAM_DESTINATIONS'),
            'allowed_actors':items('CONTENT_FACTORY_TELEGRAM_ACTORS'),
            'callback_ttl_seconds':3600,'max_attempts':3,'max_video_bytes':50_000_000}


def _validate_config(config):
    if config.get('mode') not in ('dry-run','live'):
        raise ValueError('Invalid Telegram mode')
    for key in ('allowed_destinations','allowed_actors'):
        if not isinstance(config.get(key),list) or any(not isinstance(v,str) or not 0<len(v)<=100 for v in config[key]):
            raise ValueError('Explicit Telegram allowlists required')
    for key,low,high in [('callback_ttl_seconds',60,86400),('max_attempts',1,5),('max_video_bytes',1,50_000_000)]:
        if type(config.get(key)) is not int or not low<=config[key]<=high:
            raise ValueError('Invalid Telegram limit')


def _path(delivery_id):
    if not isinstance(delivery_id,str) or not re.fullmatch('[0-9a-f]{32}',delivery_id):
        raise ValueError('Invalid delivery ID')
    return ROOT/(delivery_id+'.json')


def _write(item):
    _atomic_document(_path(item['delivery_id']),item)


def _atomic_document(path, item):
    ROOT.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        pending.write_text(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        os.replace(pending,path)
    finally:pending.unlink(missing_ok=True)


def build_review_card(job: dict, candidate_id: str, *, max_video_bytes: int=50_000_000) -> dict:
    if job.get('editorial_protocol')!=2:
        raise service.Conflict('Telegram review requires editorial protocol 2')
    row=next((r for r in service.get_editorial_view(job)['candidates'] if r['candidate_id']==candidate_id),None)
    if row is None:raise ValueError('Unknown candidate')
    if not row['artifact_id'] or not row['artifact_intact']:
        raise service.Conflict('Candidate render changed; reload before delivery')
    clip=job['candidates'][row['original_index']]
    media=None
    if row['technical_state'] in ('VALID','WARNING'):
        media=Path(clip['file'])
        if not media.is_file() or not 0<media.stat().st_size<=max_video_bytes:
            raise ValueError('Review attachment size exceeds Telegram limit; original master preserved')
    return {'schema_version':'1.0','job_id':job['id'],'candidate_id':candidate_id,
            'candidate_version':row['candidate_version'],'render_revision':row['render_revision'],
            'artifact_id':row['artifact_id'],'editorial_revision':job.get('editorial_revision',0),
            'caption':f"Candidato {row['original_index']+1} · versão {row['candidate_version']} · render {row['render_revision']}\nRevisão humana; nenhuma publicação automática.",
            'media':str(media) if media else None,'media_kind':'video/mp4' if media else None,
            'actions':list(ACTIONS)}


def queue_review_delivery(jid: str, candidate_id: str, *, destination_id: str) -> dict:
    config=load_config();_validate_config(config)
    if destination_id not in config['allowed_destinations']:
        raise PermissionError('Destination is not explicitly allowed')
    ROOT.mkdir(parents=True,exist_ok=True)
    with store.job_lock(jid):
        card=build_review_card(store.load(jid),candidate_id,max_video_bytes=config['max_video_bytes'])
        key=digest({'job':jid,'candidate':candidate_id,'artifact':card['artifact_id'],
                    'revision':card['editorial_revision'],'destination':destination_id})
        ident=key[:32]
        with store.file_lock(ROOT/'outbox.lock'):
            path=_path(ident)
            if path.exists():
                item=json.loads(path.read_text(encoding='utf-8'))
                if item['delivery_key']!=key:raise service.Conflict('Delivery key collision')
                return item
            callbacks={ident+':'+secrets.token_urlsafe(12):{'decision':action,'request_id':str(uuid.uuid4())} for action in ACTIONS}
            now=time.time()
            item={'delivery_id':ident,'delivery_key':key,'destination_id':destination_id,'card':card,
                  'callbacks':callbacks,'state':'PENDING','attempts':0,'created_at':now,
                  'expires_at':now+config['callback_ttl_seconds'],'message_id':None,'pending_comments':{}}
            _write(item)
            return item


def handle_review_callback(callback: dict, config: dict) -> dict:
    """Accept only an update from an authenticated private polling transport.

    This is not an HTTP endpoint. Actor/chat are supplied by the trusted Bot API
    update adapter, checked against local allowlists before reading the outbox.
    """
    _validate_config(config)
    allowed={'data','actor_id','destination_id','comment_raw','reasons','dimensions','content_grade','edit_requests','rejection_domain'}
    if not isinstance(callback,dict) or set(callback)-allowed:
        raise ValueError('Invalid callback fields')
    actor,destination=callback.get('actor_id'),callback.get('destination_id')
    if actor not in config['allowed_actors'] or destination not in config['allowed_destinations']:
        raise PermissionError('Telegram actor/destination is not authorized')
    token=callback.get('data')
    match=TOKEN.fullmatch(token) if isinstance(token,str) else None
    if not match:raise ValueError('Invalid opaque callback token')
    ROOT.mkdir(parents=True,exist_ok=True)
    with store.file_lock(ROOT/'outbox.lock'):
        item=json.loads(_path(match[1]).read_text(encoding='utf-8'))
        action=item['callbacks'].get(token)
        if not action or destination!=item['destination_id']:
            raise PermissionError('Callback does not belong to destination')
        if time.time()>item['expires_at']:raise service.Conflict('Callback expired; request a new card')
        decision=action['decision'];comment=callback.get('comment_raw','')
        if not isinstance(comment,str) or len(comment)>4000:raise ValueError('Invalid callback comment')
        if decision in ('REJECTED','APPROVED_WITH_ADJUSTMENTS') and not comment.strip():
            if config['mode']!='dry-run':
                item['pending_comments'][actor]=token;_write(item)
            return {'status':'COMMENT_REQUIRED','decision':decision,'delivery_id':item['delivery_id']}
        if config['mode']=='dry-run':
            return {'status':'DRY_RUN','decision':decision,'artifact_id':item['card']['artifact_id'],
                    'reason':'No human feedback written in dry-run'}
        card=item['card']
        request={'request_id':action['request_id'],'expected_editorial_revision':card['editorial_revision'],
                 'expected_artifact_id':card['artifact_id'],'decision':decision,'comment_raw':comment,
                 'reasons':callback.get('reasons',[]),'dimensions':callback.get('dimensions',{}),
                 'content_grade':callback.get('content_grade'),'edit_requests':callback.get('edit_requests',[]),
                 'rejection_domain':callback.get('rejection_domain','UNSPECIFIED') if decision=='REJECTED' else None}
    # Never wait for the job lock while holding the outbox lock: queuing uses
    # job -> outbox. The immutable service receipt bridges a crash between saves.
    result=service.review_candidate_v2(card['job_id'],card['candidate_id'],request,channel='telegram',actor_id='telegram:'+actor)
    with store.file_lock(ROOT/'outbox.lock'):
        item=json.loads(_path(match[1]).read_text(encoding='utf-8'))
        item['pending_comments'].pop(actor,None)
        item['last_event_id']=result['event']['event_id'];_write(item)
    return result


def deliver_review(delivery_id: str, config: dict, transport=None) -> dict:
    _validate_config(config)
    ROOT.mkdir(parents=True,exist_ok=True)
    with store.file_lock(ROOT/'outbox.lock'):
        item=json.loads(_path(delivery_id).read_text(encoding='utf-8'))
        if config['mode']=='dry-run':return {**item,'status':'DRY_RUN'}
        if item['destination_id'] not in config['allowed_destinations']:
            raise PermissionError('Delivery destination is not authorized')
        if item['state']=='SENT' or item['attempts']>=config['max_attempts']:return item
        if transport is None:return {**item,'status':'UNAVAILABLE'}
        if time.time()>item['expires_at']:
            item.update(state='FAILED',last_error='Expired');_write(item);return item
        # Check bytes/revision again immediately before the optional send.
        card=build_review_card(store.load(item['card']['job_id']),item['card']['candidate_id'],max_video_bytes=config['max_video_bytes'])
        if any(card[key]!=item['card'][key] for key in ('artifact_id','render_revision','editorial_revision')):
            raise service.Conflict('Delivery card is stale')
        item.update(state='SENDING',attempts=item['attempts']+1);_write(item)
        try:
            result=transport.send_review_card(copy.deepcopy(item['card']),item['destination_id'],
                [{'text':ACTIONS[p['decision']],'callback_data':token} for token,p in item['callbacks'].items()])
            if not isinstance(result,dict) or type(result.get('message_id')) is not int:
                raise ValueError('Invalid Telegram send acknowledgement')
            item.update(state='SENT',message_id=result['message_id'],sent_at=time.time())
        except (OSError,ValueError,TypeError,TimeoutError) as exc:
            item.update(state='FAILED',last_error=type(exc).__name__)
        _write(item)
        return item


def poll_once(config: dict, transport=None) -> dict:
    """One bounded private-polling iteration; default dry-run never calls transport."""
    _validate_config(config)
    if config['mode']=='dry-run':return {'status':'DRY_RUN','offset':None,'processed':[]}
    if transport is None:return {'status':'UNAVAILABLE','offset':None,'processed':[]}
    ROOT.mkdir(parents=True,exist_ok=True)
    with store.file_lock(ROOT/'poll.lock'):
        state_path=ROOT/'poll-state.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {'offset':0}
        updates=transport.get_updates(offset=state['offset'],timeout=20)
        if not isinstance(updates,list):raise ValueError('Invalid polling response')
        processed=[]
        for update in sorted(updates,key=lambda u:u.get('update_id',-1)):
            ident=update.get('update_id')
            if type(ident) is not int:raise ValueError('Invalid update ID')
            if ident<state['offset']:continue
            try:
                query=update.get('callback_query')
                message=update.get('message')
                if query:
                    chat=query.get('message',{}).get('chat',{})
                    if chat.get('type')!='private':raise PermissionError('Private review chat required')
                    normalized={'data':query.get('data'),'actor_id':str(query.get('from',{}).get('id')),
                                'destination_id':str(chat.get('id'))}
                    result=handle_review_callback(normalized,config)
                    text='Responda ao cartão com o comentário.' if result.get('status')=='COMMENT_REQUIRED' else 'Avaliação salva para este render.'
                    transport.answer_callback_query(query['id'],text)
                    status=result.get('status','REVIEW_SAVED')
                elif message:
                    chat=message.get('chat',{});actor=str(message.get('from',{}).get('id'));destination=str(chat.get('id'))
                    if chat.get('type')!='private' or actor not in config['allowed_actors'] or destination not in config['allowed_destinations']:
                        raise PermissionError('Private authorized review actor required')
                    reply=message.get('reply_to_message',{}).get('message_id');token=None
                    with store.file_lock(ROOT/'outbox.lock'):
                        for path in sorted(ROOT.glob('*.json')):
                            if not re.fullmatch('[0-9a-f]{32}',path.stem):continue
                            item=json.loads(path.read_text(encoding='utf-8'))
                            if item['destination_id']==destination and item.get('message_id')==reply:
                                token=item.get('pending_comments',{}).get(actor)
                                if token:break
                    if token:
                        handle_review_callback({'data':token,'actor_id':actor,'destination_id':destination,
                                                 'comment_raw':message.get('text','')},config)
                        status='REVIEW_SAVED'
                    else:status='IGNORED_NO_PENDING_COMMENT'
                else:status='IGNORED_UPDATE'
            except (PermissionError,ValueError,KeyError) as exc:
                # Poison/unauthorized updates are consumed, without logging content.
                status='REJECTED_'+type(exc).__name__
            except (OSError,RuntimeError):
                # Storage/transport uncertainty must retry the same stable request.
                return {'status':'RETRY_REQUIRED','offset':state['offset'],'processed':processed}
            processed.append({'update_id':ident,'status':status})
            state['offset']=ident+1
            _atomic_document(state_path,state)
        return {'status':'OK','offset':state['offset'],'processed':processed}
