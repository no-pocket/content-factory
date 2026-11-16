"""Pure editorial attempt transitions. Caller must persist under the job lock."""
import hmac
import hashlib
import math

def _time(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('invalid time')
    return value

def claim(row, *, actor, token, now, seconds):
    _time(now); _time(seconds)
    if not isinstance(actor,str) or not actor or not isinstance(token,str) or not token or seconds <= 0 or now >= row['expires_at']:
        raise ValueError('invalid claim')
    if row['state'] == 'CLAIMED' and (now < row['lease_until'] or row.get('generation_started')):
        raise ValueError('claim unavailable')
    if row['state'] not in ('REQUESTED','CLAIMED'):
        raise ValueError('claim unavailable')
    row.update(state='CLAIMED', lease_actor=actor, lease_token_hash=hashlib.sha256(token.encode('utf-8')).hexdigest(),
               lease_version=row.get('lease_version',0)+1, lease_until=min(now+seconds,row['expires_at']))

def _authorize(row, actor, token, version, now):
    _time(now)
    if (row.get('state') != 'CLAIMED' or row.get('lease_actor') != actor or
        type(version) is not int or row.get('lease_version') != version or
        not isinstance(token,str) or not hmac.compare_digest(row.get('lease_token_hash',''),hashlib.sha256(token.encode('utf-8')).hexdigest()) or
        now >= row.get('lease_until',0) or now >= row['expires_at']):
        raise ValueError('invalid or expired lease')

def begin_generation(row, *, actor, token, version, now):
    _authorize(row,actor,token,version,now)
    if row.get('generation_started'):
        raise ValueError('generation already started')
    row.update(generation_started=True,generation_started_at=now)

def expire(row, *, now):
    _time(now)
    if row['state'] == 'CLAIMED' and row.get('generation_started') and now >= row['lease_until']:
        row.update(state='EXPIRED',failure_kind='generation_result_unknown')
    elif row['state'] in ('REQUESTED','CLAIMED') and now >= row['expires_at']:
        row.update(state='EXPIRED',failure_kind='request_expired')
    else:
        raise ValueError('request not expired')

def accept_submission(row, *, actor, token, version, now, submission_id, payload_digest, outcome):
    prior=row.get('receipt')
    if prior:
        if prior['actor'] != actor or prior['submission_id'] != submission_id or prior['payload_digest'] != payload_digest:
            raise ValueError('conflicting submission')
        return dict(prior)
    _authorize(row,actor,token,version,now)
    if not row.get('generation_started') or outcome not in ('no_suitable_candidates','candidates_proposed') or not submission_id or not payload_digest:
        raise ValueError('invalid submission')
    state='NO_CANDIDATES' if outcome == 'no_suitable_candidates' else 'ACCEPTED'
    receipt={'actor':actor,'submission_id':submission_id,'payload_digest':payload_digest,'state':state}
    row.update(state=state,receipt=receipt)
    return dict(receipt)

def _locked_request(job, request_id):
    row = job.get('editorial_request')
    if job.get('status') != 'WAITING_EDITORIAL_PLAN' or not isinstance(row, dict) or row.get('request_id') != request_id:
        raise ValueError('editorial request changed')
    return row

def claim_job(jid, request_id, *, actor, now, seconds, authorize):
    """Claim a waiting request atomically; authorize must check current and frozen rights."""
    import secrets
    from . import store
    with store.job_lock(jid):
        job=store.load(jid)
        authorize(job)
        row=_locked_request(job, request_id)
        token=secrets.token_urlsafe(32)
        claim(row,actor=actor,token=token,now=now,seconds=seconds)
        store.save(job)
        return {'token':token,'version':row['lease_version'],'lease_until':row['lease_until']}

def begin_job_generation(jid, request_id, *, actor, token, version, now, authorize):
    """Persist generation start before making any provider request."""
    from . import store
    with store.job_lock(jid):
        job=store.load(jid)
        authorize(job)
        row=_locked_request(job, request_id)
        begin_generation(row,actor=actor,token=token,version=version,now=now)
        store.save(job)

def submit_job_plan(jid, plan, *, actor, token, version, now, authorize):
    """Persist a validated response and receipt in one atomic job replacement."""
    import json
    from . import store
    from .artifacts import digest
    from .editorial_plan import validate_editorial_plan
    if not isinstance(plan, dict) or not isinstance(plan.get('submission_id'), str):
        raise ValueError('invalid submission')
    payload_digest=digest(plan)
    with store.job_lock(jid):
        job=store.load(jid)
        row=job.get('editorial_request')
        if not isinstance(row, dict) or row.get('job_id') != jid:
            raise ValueError('editorial request missing')
        # Receipt replay is authenticated by the trusted actor, even after lease expiry
        # or revoked source access, and never returns transcript or plan contents.
        if row.get('receipt'):
            return accept_submission(row,actor=actor,token=token,version=version,now=now,
                submission_id=plan['submission_id'],payload_digest=payload_digest,outcome=plan.get('outcome'))
        authorize(job)
        row=_locked_request(job,plan.get('request_id'))
        _authorize(row,actor,token,version,now)
        if not row.get('generation_started'):
            raise ValueError('generation not started')
        for key in ('job_id','run_id','editorial_attempt_id'):
            if key in plan and plan[key] != row.get(key):
                raise ValueError('stale editorial identity')
        transcript=json.loads((store.JOBS / (jid+'.transcript.json')).read_text(encoding='utf8'))
        try:
            validated=validate_editorial_plan(plan,row,transcript)
        except ValueError as exc:
            reason_codes={
                'segment outside source or duration policy':'segment_out_of_bounds',
                'anchor does not exist':'anchor_not_found',
                'anchor does not match source interval':'anchor_mismatch',
                'source mismatch':'source_mismatch',
                'transcript mismatch':'transcript_mismatch',
                'unsupported direction':'unsupported_direction',
                'only one continuous segment is supported':'unsupported_segments',
            }
            receipt={'actor':actor,'submission_id':plan['submission_id'],
                     'payload_digest':payload_digest,'state':'INVALID'}
            row.update(state='INVALID',failure_kind='invalid_plan',
                       failure_code=reason_codes.get(str(exc),'invalid_plan_schema'),failed_at=now,receipt=receipt)
            if row.get('fallback_allowed') is True:
                row['fallback_pending']=True
            else:
                job.update(status='FAILED',error='Plano editorial inválido; fallback desativado')
            store.save(job)
            return dict(receipt)
        receipt=accept_submission(row,actor=actor,token=token,version=version,now=now,
            submission_id=validated['submission_id'],payload_digest=payload_digest,outcome=validated['outcome'])
        row['plan']=validated
        row['accepted_at']=now
        if receipt['state']=='NO_CANDIDATES':
            job['status']='EDITORIAL_NO_CANDIDATES'
            runs=job.get('processing_runs') or []
            if runs and runs[-1].get('run_id') == row.get('run_id') and runs[-1].get('state') == 'RUNNING':
                runs[-1].update(state='EDITORIAL_NO_CANDIDATES', finished_at=now)
        else:
            row['resume_pending']=True
        store.save(job)
        return receipt

def prepare_waiting_request(job, transcript, duration, settings, *, now, timeout):
    """Freeze one editorial request for a run; caller persists the complete job."""
    import re
    import uuid
    from .editorial_plan import transcript_digest
    _time(now); _time(timeout); _time(duration)
    if timeout <= 0 or duration <= 0 or not re.fullmatch(r'[0-9a-f]{64}',job.get('source_fingerprint','')):
        raise ValueError('invalid editorial request source')
    runs=job.get('processing_runs') or []
    if not runs or not isinstance(runs[-1].get('run_id'),str):
        raise ValueError('missing processing run')
    identity={'job_id':job['id'],'run_id':runs[-1]['run_id'],
              'source_fingerprint':job['source_fingerprint'],'duration_ms':round(duration*1000),
              'transcript_digest':transcript_digest(transcript),'min_seconds':settings['min_seconds'],
              'max_seconds':settings['max_seconds']}
    previous=job.get('editorial_request')
    if previous:
        if any(previous.get(k) != v for k,v in identity.items()):
            raise ValueError('editorial request identity changed')
        return previous
    row={**identity,'request_id':str(uuid.uuid4()),'editorial_attempt_id':str(uuid.uuid4()),
         'state':'REQUESTED','created_at':now,'expires_at':now+timeout,'lease_version':0,
         'generation_started':False,'canonicalization':'cf-transcript-v1',
         'layout_presets':['legacy'],'subtitle_presets':['bold_karaoke_v1'],
         'fallback_allowed':settings.get('editorial_fallback_local',True)}
    job['editorial_request']=row
    job['status']='WAITING_EDITORIAL_PLAN'
    return row

def start_editorial_if_eligible(job, transcript, duration, settings, *, now, authorize):
    if settings.get('editorial_planner') != 'hermes_first':
        return False
    snapshot=job.get('source_snapshot')
    if not isinstance(snapshot,dict) or 'external' not in snapshot.get('allowed_model_scopes',[]) or not authorize(job):
        job['editorial_planner_fallback']='source_scope_forbids_external'
        if settings.get('editorial_fallback_local',True) is not True:
            raise PermissionError('External source authorization unavailable; local fallback disabled')
        return False
    prepare_waiting_request(job,transcript,duration,settings,now=now,timeout=900)
    return True

def materialize_candidates(plan, transcript):
    """Translate already-validated proposals without using model text as transcript."""
    import copy
    if plan.get('outcome','candidates_proposed') != 'candidates_proposed':
        raise ValueError('plan has no proposed candidates')
    result=[]
    for proposal in plan['candidates']:
        segment=proposal['segments'][0]
        start,end=segment['source_in_ms']/1000,segment['source_out_ms']/1000
        text=' '.join(s['text'].strip() for s in transcript['segments']
                      if s['start'] < end and s['end'] > start and s.get('text','').strip())
        if not text:
            raise ValueError('candidate has no transcript')
        result.append({'start':start,'end':end,'text':text,'title':proposal['editorial_title'],
                       'score':0,'reason':proposal['intent'],'proposal_source':'hermes',
                       'editorial_plan':copy.deepcopy(proposal),
                       'boundary_review_required':segment['boundary_status']=='requires_audio_review'})
    return result

def reconcile_accepted_plan(jid, *, queue=None):
    """Recover persisted accepted-plan handoff without duplicating Redis entries."""
    from . import store
    from .source_ingestion import recover_import_enqueue
    with store.job_lock(jid):
        job=store.load(jid)
        row=job.get('editorial_request') or {}
        if row.get('state') != 'ACCEPTED' or row.get('resume_pending') is not True:
            return job
        if job['status']=='WAITING_EDITORIAL_PLAN':
            from .queueing import PROCESSING
            if (queue or store.rconn()).lpos(PROCESSING, jid) is not None:
                return job
            job['status']='QUEUED'
            store.save(job)
        elif job['status'] != 'QUEUED':
            return job
    return recover_import_enqueue(jid,queue=queue)

def verify_frozen_inputs(job, transcript, source):
    """Verify immutable inputs again before any resumed processing."""
    from .editorial_plan import transcript_digest
    row=job.get('editorial_request') or {}
    runs=job.get('processing_runs') or []
    if not runs or runs[-1].get('run_id') != row.get('run_id'):
        raise ValueError('editorial run changed')
    if row.get('transcript_digest') != transcript_digest(transcript):
        raise ValueError('editorial transcript changed')
    with source.open('rb') as handle:
        actual=hashlib.file_digest(handle,'sha256').hexdigest()
    if actual != row.get('source_fingerprint') or actual != job.get('source_fingerprint'):
        raise ValueError('editorial source changed')
    return row


def resume_accepted_plan(job, transcript, source):
    row=verify_frozen_inputs(job,transcript,source)
    if row.get('state') != 'ACCEPTED' or row.get('resume_pending') is not True:
        raise ValueError('editorial plan is not accepted')
    return materialize_candidates(row['plan'],transcript)


def reconcile_editorial_requests(*, queue=None):
    from . import store
    from .hermes_api import _external_allowed
    import time
    for job in store.all_jobs():
        row=job.get('editorial_request') or {}
        if row.get('state')=='ACCEPTED' and row.get('resume_pending') is True and job.get('status') in ('WAITING_EDITORIAL_PLAN','QUEUED'):
            reconcile_accepted_plan(job['id'],queue=queue)
        elif row.get('state') in ('REQUESTED','CLAIMED','EXPIRED','INVALID') and job.get('status') in ('WAITING_EDITORIAL_PLAN','QUEUED'):
            expire_job_request(job['id'],now=time.time(),queue=queue,authorize_local=authorize_local_source,
                               authorize_external=_external_allowed)


def authorize_local_source(job):
    from .source_ingestion import require_active_source
    from .source_registry import get_source
    snapshot=job.get('source_snapshot')
    if not isinstance(snapshot,dict): raise PermissionError('Missing source snapshot')
    require_active_source(snapshot)
    current=get_source(snapshot['channel_id'])
    require_active_source(current)
    if any('local' not in source.get('allowed_model_scopes', []) for source in (snapshot, current)):
        raise PermissionError('Local model scope is not authorized')

def hermes_direction(clip):
    """Translate the supported v1 editorial direction into timeline hints."""
    proposal=clip['editorial_plan']; direction=proposal['direction']
    if direction != {'layout_preset_id':'legacy','subtitle_preset_id':'bold_karaoke_v1',
                     'pacing':'natural','word_highlight':'only_if_word_timing_reliable'}:
        raise ValueError('unsupported Hermes direction')
    return {'hook':proposal['editorial_title'],'pace':'natural','effects':[],'broll':[]}


def expire_job_request(jid, *, now, queue=None, authorize_local, authorize_external=None):
    """Persist expiry and one local fallback intent under the job lock."""
    from . import store
    from .queueing import PROCESSING
    from .source_ingestion import recover_import_enqueue
    with store.job_lock(jid):
        job=store.load(jid); row=job.get('editorial_request') or {}
        if (row.get('state') in ('REQUESTED','CLAIMED','EXPIRED','INVALID') and
                authorize_external is not None and not authorize_external(job)):
            row.update(state='REVOKED',failure_kind='source_authorization_revoked')
            job.update(status='FAILED',error='Autorização externa da fonte revogada')
            store.save(job)
            return job
        if row.get('state') in ('REQUESTED','CLAIMED'):
            try:
                expire(row,now=now)
            except ValueError:
                return job
            if row.get('fallback_allowed') is True:
                try:
                    authorize_local(job)
                except (PermissionError,KeyError,ValueError):
                    row.update(state='REVOKED',failure_kind='source_authorization_revoked')
                    job.update(status='FAILED',error='Autorização da fonte indisponível')
                else:
                    row['fallback_pending']=True
                    job['editorial_planner_fallback']=row['failure_kind']
            else:
                job.update(status='FAILED',error='Planejamento editorial expirou; fallback desativado')
            store.save(job)
        if row.get('state') not in ('EXPIRED','INVALID') or row.get('fallback_pending') is not True:
            return job
        try:
            authorize_local(job)
        except (PermissionError,KeyError,ValueError):
            row.update(state='REVOKED',failure_kind='source_authorization_revoked')
            job.update(status='FAILED',error='Autorização da fonte indisponível')
            store.save(job)
            return job
        job['editorial_planner_fallback']=row.get('failure_kind','UNKNOWN')
        if job['status']=='WAITING_EDITORIAL_PLAN':
            if (queue or store.rconn()).lpos(PROCESSING,jid) is not None:
                return job
            job['status']='QUEUED'
            store.save(job)
        elif job['status']!='QUEUED':
            return job
    return recover_import_enqueue(jid,queue=queue)
