"""Five authorized sources, cached ASR, private K4200/Qwen 2.5 1.5B engine.

Checkpoint results after every job; never consume production Redis or overwrite parents.
Run once and follow the same process handle. No model downloads or image builds.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
import sys
import uuid
import urllib.request
from pathlib import Path

from research.pilot_approved_style_gpu import run

PARENTS = ['255f7f42-5d82-45ae-9707-0fa142c2d985',
           '583bd5d7-6373-4e21-8926-7fd1b02dc914',
           '127b2a1a-c5c5-451e-88bf-f4ad3cb22a39',
           'a5f108ff-c572-42db-905a-a73def7c4ba1',
           '7256c7f7-ab16-464b-8314-ce84e138f0e1']


def completed_entry(job, parent, seconds):
    if job['status'] not in {'NEEDS_REVIEW','PARTIAL_FAILED','FAILED'}:
        raise RuntimeError('Worker did not process job: '+job['id']+' '+job['status'])
    entry={'id':job['id'],'parent':parent,'name':job['original_name'],'language':job.get('language'),
           'status':job['status'],'ranker_used':job.get('ranker_used'),'seconds':seconds,
           'candidates':[{k:c.get(k) for k in ('start','end','state','director_used','renderer_used','word_count')}
                         for c in job['candidates']]}
    entry['gpu_and_remotion_complete']=(bool(entry['candidates']) and entry['ranker_used']=='kepler_gpu' and
        all(c['director_used']=='kepler_gpu' and c['renderer_used']=='remotion' for c in entry['candidates']))
    return entry


def wait_for_production_gpu():
    for _ in range(180):
        try:
            with urllib.request.urlopen('http://127.0.0.1:11436/health',timeout=3) as response:
                if json.load(response).get('status')=='ok':return True
        except (OSError,ValueError):pass
        time.sleep(1)
    return False


def restore_production(paused):
    errors=[]
    gpu_healthy=False
    for name in reversed(paused):
        try:
            run('docker','start',name)
            if name.endswith('kepler-engine-1'):
                gpu_healthy=wait_for_production_gpu()
                if not gpu_healthy:errors.append('GPU health timeout after restart')
        except Exception as exc:
            errors.append(name+': '+str(exc)[:400])
    running=[]
    for name in paused:
        try:running.append(run('docker','inspect','--format','{{.State.Running}}',name)=='true')
        except Exception as exc:
            running.append(False);errors.append(name+': '+str(exc)[:400])
    return {'production_services_running':all(running),'production_gpu_healthy':gpu_healthy,
            'restoration_errors':errors}


def main():
    root = Path(__file__).resolve().parents[1]
    data = root/'data'
    destination = root/'research/sprint/gpu-five-results.json'
    resume = {}
    retained = []
    previous_tests = []
    parents_to_run = PARENTS
    retry = '--retry-fallbacks' in sys.argv
    if destination.exists():
        previous=json.loads(destination.read_text(encoding='utf-8'))
        if retry:
            if previous['status']!='COMPLETED_WITH_ISSUES' or previous.get('bounded_retry'):
                raise RuntimeError('Only one bounded retry of a completed batch is allowed')
            retained=[e for e in previous['jobs'] if e['gpu_and_remotion_complete']]
            previous_tests=[e for e in previous['jobs'] if not e['gpu_and_remotion_complete']]
            parents_to_run=[e['parent'] for e in previous_tests]
            assert parents_to_run
            destination.with_name('gpu-five-first-pass.json').write_bytes(destination.read_bytes())
        elif '--resume-unprocessed' not in sys.argv or previous['status']=='RUNNING':
            raise RuntimeError('Existing batch report; inspect it instead of starting duplicate jobs')
        else:
            for entry in previous['jobs']:
                job=json.loads((data/'work'/(entry['id']+'.json')).read_text(encoding='utf-8'))
                if job['status']!='TRANSCRIBING' or job['candidates'] or job.get('processing_runs'):
                    raise RuntimeError('Only never-processed harness jobs can resume here')
                resume[entry['parent']]=entry['id']
            assert set(resume)==set(PARENTS)
            destination.with_name('gpu-five-initial-harness.json').write_bytes(destination.read_bytes())
    for key in ('clips:queue', 'clips:processing'):
        assert run('docker','exec','content-factory-redis-1','redis-cli','LLEN',key) == '0'
    tag = 'qwen2.5:1.5b'
    filename = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
    models = Path(r'E:\CodexFiles\chat-local-k4200\models')
    with (models/filename).open('rb') as handle:
        model_hash = hashlib.file_digest(handle,'sha256').hexdigest()
    parent_hashes = {jid:hashlib.sha256((data/'work'/(jid+'.json')).read_bytes()).hexdigest() for jid in PARENTS}
    approved = ['7cb2fb21-353c-4805-9fbb-b3c10603be44','700982a4-ca3d-4f4a-be5f-887d9cf08a29']
    approved_hashes = {jid:hashlib.sha256((data/'work'/(jid+'.json')).read_bytes()).hexdigest() for jid in approved}
    settings = {'clip_count':3,'target_seconds':30,'min_seconds':18,'max_seconds':45,
                'proposal_max_chunks':2,'shortlist':5,'ollama_timeout':300,'whisper_model':'base',
                'ranker_mode':'ollama','llm_backend':'kepler_gpu','llm_model':tag,
                'director_mode':'ollama','render_engine':'remotion','render_quality':'high'}
    report = {'cohort':'gpu-five-2026-11-06','model':tag,'model_filename':filename,'model_sha256':model_hash,
              'settings':settings,'transcription_reused':True,'source_parents':PARENTS,
              'status':'RUNNING','jobs':retained,'editorial_verdict':None,'bounded_retry':retry,
              'diagnostic_previous_tests':previous_tests}
    def checkpoint():
        pending = destination.with_suffix('.pending')
        pending.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        pending.replace(destination)
    checkpoint()
    suffix = uuid.uuid4().hex[:8]
    network, engine, bridge = ('cf-five-'+suffix,'cf-five-engine-'+suffix,'cf-five-bridge-'+suffix)
    active = []
    paused = []
    network_created = False
    try:
        for name in ('content-factory-worker-1','content-factory-kepler-engine-1'):
            if run('docker','inspect','--format','{{.State.Running}}',name) == 'true':
                paused.append(name)
                run('docker','stop',name)
        run('docker','network','create',network); network_created=True
        run('docker','run','-d','--name',engine,'--network',network,'--network-alias','kepler-engine',
            '--gpus','all','-v','cf_kepler_b4300:/build:ro','-v',str(models)+':/pilot-models:ro',
            '-e','LD_LIBRARY_PATH=/build/bin:/usr/local/cuda-10.2/lib64','--entrypoint','/build/bin/llama-server',
            'content-factory-kepler-lab:cuda10.2','-m','/pilot-models/'+filename,'--host','0.0.0.0','--port','8080',
            '--ctx-size','4096','--batch-size','512','--ubatch-size','256','--gpu-layers','99','--threads','4')
        active.append(engine)
        run('docker','run','-d','--name',bridge,'--network',network,'--network-alias','kepler-bridge',
            '-p','127.0.0.1::11434','-v',str(root/'app/kepler_bridge.py')+':/opt/bridge.py:ro',
            '-e','KEPLER_MODEL='+tag,'-e','KEPLER_ENGINE_URL=http://kepler-engine:8080',
            '-e','KEPLER_REQUEST_TIMEOUT=300','--entrypoint','python','content-factory-worker:latest',
            '/opt/bridge.py','bridge')
        active.append(bridge)
        port = int(run('docker','port',bridge,'11434/tcp').rsplit(':',1)[1])
        for _ in range(180):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=3) as response:
                    if json.load(response).get('status') == 'ok':break
            except (OSError,ValueError):pass
            time.sleep(1)
        else:raise RuntimeError('Private GPU did not become healthy')
        report['gpu_engine'] = engine
        report['gpu_memory_loaded'] = run('nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader')
        checkpoint()
        for parent in parents_to_run:
            job_settings={**settings,'shortlist':3} if retry else settings
            payload = {'parent':parent,'settings':job_settings,'model_sha256':model_hash,'cohort':report['cohort'],
                       'resume_id':resume.get(parent),'retry':retry}
            code = """import json,sys,hashlib;from pathlib import Path
from app.store import JOBS,load,new_job,save
from app.worker import process
p=json.loads(sys.argv[1]);parent=load(p['parent'])
source=Path(parent['source'])
with source.open('rb') as f:fingerprint=hashlib.file_digest(f,'sha256').hexdigest()
if fingerprint!=parent.get('source_fingerprint'):raise ValueError('Source hash differs from frozen corpus')
t=JOBS/(parent['id']+'.transcript.json')
j=load(p['resume_id']) if p['resume_id'] else new_job(source,'GPU 5 vídeos · '+('retentativa GPU · ' if p['retry'] else '')+parent['original_name'],parent['creator'],parent['license_note'],settings=p['settings'])
if p['resume_id'] and (j['candidates'] or j.get('processing_runs')):raise ValueError('Resume would overwrite processed work')
j.update(status='QUEUED',source_parent_job=parent['id'],source_fingerprint=fingerprint,
         qc_settings=parent['qc_settings'],pipeline_version='gpu-five-title-ending-v1',
         model_artifact_sha256=p['model_sha256'],evaluation={'cohort':p['cohort'],'variant':'qwen1.5b-gpu-remotion-high'+('-shortlist3' if p['retry'] else '')})
save(j);(JOBS/(j['id']+'.transcript.json')).write_bytes(t.read_bytes())
print('BATCH_JOB '+j['id'],flush=True);process(j['id'])
print('BATCH_RESULT '+json.dumps(load(j['id']),ensure_ascii=False),flush=True)
"""
            started = time.monotonic()
            # Output retained in a log so process IDs remain observable while rendering.
            logpath = root/'research/sprint'/('gpu-five-'+parent[:8]+('-retry' if retry else '')+'.log')
            with logpath.open('w',encoding='utf-8') as log:
                result = subprocess.run(['docker','run','--rm','--name','cf-five-worker-'+suffix,'--network',network,
                    '-v',str(data)+':/data','-v',str(root/'app')+':/app/app:ro',
                    '-v',str(root/'renderer/src')+':/app/renderer/src:ro',
                    '-e','DATA_DIR=/data','-e','KEPLER_BRIDGE_URL=http://kepler-bridge:11434',
                    '-e','RENDER_TIMEOUT=900','--entrypoint','python','content-factory-worker:latest',
                    '-c',code,json.dumps(payload)],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError('Test worker failed; inspect '+str(logpath))
            line=next(line for line in logpath.read_text(encoding='utf-8').splitlines() if line.startswith('BATCH_RESULT '))
            job=json.loads(line.removeprefix('BATCH_RESULT '))
            entry=completed_entry(job,parent,round(time.monotonic()-started,3))
            entry['settings']=job['settings']
            report['jobs'].append(entry);checkpoint();print(json.dumps(entry,ensure_ascii=False),flush=True)
        report['status']='COMPLETED' if all(e['gpu_and_remotion_complete'] and e['status']=='NEEDS_REVIEW' for e in report['jobs']) else 'COMPLETED_WITH_ISSUES'
    except Exception as exc:
        report.update(status='FAILED',error=str(exc));raise
    finally:
        for name in reversed(active):subprocess.run(['docker','rm','-f',name],capture_output=True)
        if network_created:subprocess.run(['docker','network','rm',network],capture_output=True)
        report.update(restore_production(paused))
        report['parents_unchanged']=all(hashlib.sha256((data/'work'/(jid+'.json')).read_bytes()).hexdigest()==h for jid,h in parent_hashes.items())
        report['approved_records_unchanged']=all(hashlib.sha256((data/'work'/(jid+'.json')).read_bytes()).hexdigest()==h for jid,h in approved_hashes.items())
        checkpoint();print('Batch terminal; production restoration: '+json.dumps({k:report[k] for k in ('production_services_running','production_gpu_healthy','restoration_errors')}),flush=True)


if __name__ == '__main__':main()
