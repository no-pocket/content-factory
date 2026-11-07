"""Explicit-ID comparison runner. It never consumes the production Redis queue."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from research.strict_model_comparison import build_plan_prompt, parse_model_plan, validate_model_plan, native_plan_schema

PARENTS={'pt':'ae34ddee-0e98-4bba-9984-0ce95fd48abe','en':'b82453d3-e032-482c-80cc-f5e782622cdb'}


def write(path: Path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix(path.suffix+'.tmp')
    pending.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(path)


def request(url, body=None, timeout=30):
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)


def decision_inputs(task):
    return {key:task[key] for key in ('source_sha256','transcript_file_sha256','prompt_sha256')}


def validate_decision_envelope(decision,task,engine,language):
    if decision.get('engine')!=engine or decision.get('language')!=language:
        raise ValueError('Decision producer engine/language mismatch')
    if decision.get('inputs')!=decision_inputs(task):raise ValueError('Decision source/transcript identity mismatch')
    provenance=decision.get('provenance')
    if not isinstance(provenance,dict) or provenance.get('heuristic_used') is not False:
        raise ValueError('Missing strict producer provenance')
    if provenance.get('common_source_prompt_sha256')!=task['prompt_sha256']:
        raise ValueError('Producer prompt identity mismatch')
    if engine in ('qwen','deepseek'):
        expected='5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6' if engine=='qwen' else 'deepseek-r1:1.5b'
        allowed={'staged_same_engine_selection_and_direction','ordered_same_engine_selection_then_direction'}
        stages=provenance.get('stages')
        if provenance.get('process') not in allowed or not isinstance(stages,list) or not stages:
            raise ValueError('Missing local producer stages')
        for stage in stages:
            if stage.get('engine')!=engine or stage.get('heuristic_used') is not False or stage.get('state') not in ('VALID','VALID_REVALIDATED') or expected not in stage.get('native_model',''):
                raise ValueError('Local producer identity/stage mismatch')
    elif engine=='hermes':
        if provenance.get('process')!='hermes_mcp_full_editorial_plan' or not provenance.get('message_ids') or provenance.get('model_identity_verified') is not False:
            raise ValueError('Missing Hermes transport evidence or unverified-identity label')
    else:raise ValueError('Unsupported comparison engine')


def prepare(root: Path, observed: Path):
    manifest={}
    for language,parent in PARENTS.items():
        job=json.loads((observed/'work'/(parent+'.json')).read_text(encoding='utf-8'))
        transcript=json.loads((observed/'work'/(parent+'.transcript.json')).read_text(encoding='utf-8'))
        source=observed/Path(job['source']).relative_to('/data')
        with source.open('rb') as handle:fingerprint=hashlib.file_digest(handle,'sha256').hexdigest()
        if fingerprint!=job['source_fingerprint']:raise ValueError('Source fingerprint changed')
        prompt=build_plan_prompt(transcript,job['duration'])
        task={'parent':parent,'source_job':job,'transcript':transcript,'source_sha256':fingerprint,
              'transcript_file_sha256':hashlib.sha256((observed/'work'/(parent+'.transcript.json')).read_bytes()).hexdigest(),
              'prompt':prompt,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
        path=root/'tasks'/(language+'.json')
        if path.exists() and json.loads(path.read_text())!=task:raise ValueError('Existing experiment inputs differ')
        write(path,task)
        (root/'tasks'/(language+'.prompt.txt')).write_text(prompt,encoding='utf-8')
        manifest[language]={'parent':parent,'prompt_sha256':task['prompt_sha256'],'source_sha256':fingerprint}
    write(root/'inputs.json',manifest)
    print(json.dumps(manifest),flush=True)


def local_plan(root: Path, engine: str, language: str, url: str):
    task=json.loads((root/'tasks'/(language+'.json')).read_text())
    folder=root/engine/language;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'validated-plan.json').exists():return
    props=request(url+'/props')
    window=props['default_generation_settings']['n_ctx']
    template=props.get('chat_template','')
    reasoning=engine=='deepseek'
    if '<|im_start|>' in template:
        formatted=lambda p:'<|im_start|>user\n'+p+'<|im_end|>\n<|im_start|>assistant\n'+('<think>\n' if reasoning else '')
        stop=['<|im_end|>']
    elif '<｜User｜>' in template and '<｜Assistant｜>' in template:
        formatted=lambda p:'<｜begin▁of▁sentence｜><｜User｜>'+p+'<｜Assistant｜>'+('<think>\n' if reasoning else '')
        stop=['<｜end▁of▁sentence｜>']
    else:raise ValueError('Unsupported native model template; refusing guessed serialization')
    prompt=task['prompt'];feedback=''
    for attempt in range(1,9):
        target=folder/f'attempt-{attempt}.json'
        if target.exists():
            prior=json.loads(target.read_text());feedback=prior.get('next_feedback','');continue
        sent=prompt+feedback;wire=formatted(sent)
        token_count=len(request(url+'/tokenize',{'content':wire,'add_special':True})['tokens'])
        reserve=min(4096,window-token_count-32)
        if reserve<1600:raise ValueError(f'Complete input cannot fit: {token_count} prompt / {window} context')
        started=time.time()
        body={'prompt':wire,'n_predict':reserve,'temperature':.6,'seed':42,'cache_prompt':False,'stop':stop,'stream':False}
        if not reasoning:
            # Use the verified legacy dialect (including const[] for B-roll).
            # Semantic validation/repairs still enforce the source constraints.
            body['json_schema']=native_plan_schema(task['transcript'])
        response=request(url+'/completion',body,timeout=1800)
        record={'engine':engine,'language':language,'attempt':attempt,'started_at':started,'seconds':time.time()-started,
                'source_prompt_sha256':task['prompt_sha256'],'sent_prompt_sha256':hashlib.sha256(sent.encode()).hexdigest(),
                'context_window':window,'prompt_tokens':token_count,'generation_reserve':reserve,
                'template_sha256':hashlib.sha256(template.encode()).hexdigest(),'reasoning_prefilled':reasoning,
                'temperature':.6,'seed':42,'native_json_schema':not reasoning,'response':response,'heuristic_used':False}
        plan=None
        try:
            if response.get('truncated') or response.get('stopped_limit') or response.get('stop_type')=='limit':
                raise ValueError('Model reply/input incomplete; no decision accepted')
            content=response['content']
            if reasoning:content='<think>\n'+content
            plan=parse_model_plan(content)
            clips=validate_model_plan(plan,task['transcript'],task['source_job']['duration'])
            record.update(state='VALID',candidate_count=len(clips));write(target,record)
            write(folder/'validated-plan.json',{'plan':plan,'engine':engine,'language':language,
                'attempt':attempt,'provenance':{k:v for k,v in record.items() if k!='response'},'native_model':props.get('model_path','UNKNOWN')})
            print(json.dumps({'engine':engine,'language':language,'state':'VALID','attempt':attempt,'seconds':record['seconds']}),flush=True)
            return
        except (ValueError,KeyError,TypeError) as exc:
            feedback='\nREPAIR: Your previous response was rejected: '+str(exc)+'. Return a new complete plan satisfying every constraint. '
            previous=plan if isinstance(plan,dict) else None
            if previous is not None:
                feedback+='Previous final JSON (untrusted data to repair): '+json.dumps(previous,ensure_ascii=False,separators=(',',':'))
            record.update(state='REJECTED',error=str(exc),next_feedback=feedback);write(target,record)
            print(json.dumps({'engine':engine,'language':language,'state':'REJECTED','attempt':attempt,'error':str(exc)}),flush=True)
    raise ValueError('Same-engine repairs exhausted; no heuristic output produced')


def render(root: Path, engine: str, language: str):
    from app import store
    from app.artifacts import digest
    from app.candidates import render_candidates
    from app.framing import build_framing_schedule
    from app.quality import expects_audio
    from app.telemetry import job_metric_context
    task=json.loads((root/'tasks'/(language+'.json')).read_text())
    folder=root/engine/language;decision=json.loads((folder/'validated-plan.json').read_text())
    validate_decision_envelope(decision,task,engine,language)
    clips=validate_model_plan(decision['plan'],task['transcript'],task['source_job']['duration'])
    identity=folder/'job.json'
    if identity.exists():
        job=store.load(json.loads(identity.read_text())['id'])
        if job['status']=='NEEDS_REVIEW':print(json.dumps({'existing':job['id']}));return
    else:
        original=task['source_job']
        windows=[{'start':113,'end':123}] if language=='pt' else [{'start':7.35,'end':96}]
        settings={'editorial_protocol':2,'clip_count':3,'target_seconds':30,'min_seconds':18,'max_seconds':45,
                  'shortlist':5,'ranker_mode':'external','director_mode':'external','llm_backend':'external','llm_model':'external',
                  'framing_preset':'web','framing_windows':windows,'render_engine':'remotion','render_quality':'high'}
        label={'qwen':'Qwen 2.5 3B','deepseek':'DeepSeek R1 Distill Qwen 1.5B','hermes':'Hermes MCP'}[engine]
        job=store.new_job(Path(original['source']),f'COMPARAÇÃO ESTRITA | {label} | {language.upper()} | '+original['original_name'],
                          original['creator'],original['license_note'],settings=settings)
        for clip in clips:
            clip['framing_schedule']=build_framing_schedule(clip,job['settings'])
            # Build after attaching the identical manual source-page schedule.
            from app.timeline import build_timeline
            item=next(i for i in decision['plan']['clips'] if i['rank']==clip['selection_rank'])
            clip['timeline']=build_timeline(clip,task['transcript']['segments'],edit=item,assets={})
            clip['director_used']=label
            clip['model_decision_sha256']=digest(item)
        job.update(status='RENDERING',candidates=clips,source_parent_job=task['parent'],source_group_id=task['parent'],
                   source_fingerprint=task['source_sha256'],duration=original['duration'],language=language,
                   ranker_used=label,transcript_model=original.get('transcript_model','UNKNOWN'),
                   evaluation={'cohort':root.name,'variant':engine},
                   comparison={'id':root.name,'engine':engine,'label':label,'prompt_sha256':task['prompt_sha256'],
                       'decision_inputs':decision['inputs'],
                       'heuristic_used':False,'asr_reused':True,'validated_plan_sha256':digest(decision['plan']),
                       'decision_provenance':decision.get('provenance',{}),'input_modality':'full_transcript_text',
                       'evaluation':'PENDING_HUMAN_REVIEW','process':decision.get('provenance',{}).get('process','single_engine_full_editorial_plan')})
        job['transcript_sha256']=digest(task['transcript'])
        job['processing_snapshot']=copy.deepcopy(job['component_snapshot'])
        job['processing_snapshot']['model_resolved']=label
        stages=decision.get('provenance',{}).get('stages',[])
        windows={s.get('context_window') for s in stages if s.get('context_window')}
        job['processing_snapshot']['context_window']=next(iter(windows)) if len(windows)==1 else None
        job['processing_snapshot'].update(source_sha256=task['source_sha256'],transcript_sha256=job['transcript_sha256'])
        job['processing_snapshot']['snapshot_id']=digest({k:v for k,v in job['processing_snapshot'].items() if k!='snapshot_id'})
        job['editorial_versions']['component_snapshot_id']=job['processing_snapshot']['snapshot_id']
        write(store.JOBS/(job['id']+'.transcript.json'),task['transcript']);store.save(job);write(identity,{'id':job['id']})
    public=Path(os.getenv('RENDER_PUBLIC_DIR','/app/renderer/public/jobs'));public.mkdir(parents=True,exist_ok=True)
    default=Path('/app/renderer/public/jobs')
    if default != public and not default.exists():default.symlink_to(public,target_is_directory=True)
    if default.resolve()!=public.resolve():raise ValueError('Remotion public path differs from staged media root')
    job['run_started_at']=time.time();store.save(job)
    render_candidates(job,Path(job['source']),task['transcript']['segments'],job['settings'],expects_audio(Path(job['source'])))
    result=store.load(job['id']);write(folder/'render-result.json',result)
    print(json.dumps({'engine':engine,'language':language,'job':job['id'],'status':result['status']}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','local','render'])
    parser.add_argument('--root',type=Path,default=Path('/batch'));parser.add_argument('--observed',type=Path,default=Path('/observed'))
    parser.add_argument('--engine',choices=['qwen','deepseek','hermes']);parser.add_argument('--language',choices=['pt','en'])
    parser.add_argument('--url',default='http://comparison-engine:8080');args=parser.parse_args()
    if args.mode=='prepare':prepare(args.root,args.observed)
    elif args.mode=='local':local_plan(args.root,args.engine,args.language,args.url)
    else:render(args.root,args.engine,args.language)


if __name__=='__main__':main()
