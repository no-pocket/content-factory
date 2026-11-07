"""Two small GPU+Remotion trials using existing GGUFs and approved source word timings.

Never changes the approved job. Pauses/restores the production GPU and worker only
with an empty queue; test workers process explicit IDs, never consume the queue.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
import uuid
import urllib.request
from pathlib import Path


def run(*args, timeout=None):
    result=subprocess.run(list(args),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:] or result.stdout[-2500:])
    return result.stdout.strip()


def main():
    root=Path(__file__).resolve().parents[1]
    data=root/'data'; models=Path(r'E:\CodexFiles\chat-local-k4200\models')
    kept='7cb2fb21-353c-4805-9fbb-b3c10603be44'
    reference=json.loads((data/'work'/(kept+'.json')).read_text(encoding='utf-8'))
    before=hashlib.sha256((data/'work'/(kept+'.json')).read_bytes()).hexdigest()
    for queue in ('clips:queue','clips:processing'):
        assert run('docker','exec','content-factory-redis-1','redis-cli','LLEN',queue)=='0','Wait for current jobs'
    suffix=uuid.uuid4().hex[:8]; network='cf-gpu-style-'+suffix
    excerpt='gpu_style_reference_'+suffix+'.mkv'
    run('docker','run','--rm','--network','none','-v',str(data)+':/data','--entrypoint','ffmpeg',
        'content-factory-worker:latest','-v','error','-nostdin','-i',reference['source'],'-t','60',
        '-map','0:v:0','-map','0:a:0','-c','copy','/data/input/'+excerpt)
    transcript=json.loads((data/'work'/(kept+'.transcript.json')).read_text(encoding='utf-8'))
    segments=[s for s in transcript['segments'] if s['start']>=0 and s['end']<=60]
    assert segments and all(s.get('words') for s in segments)
    with (data/'input'/excerpt).open('rb') as handle:
        fingerprint=hashlib.file_digest(handle,'sha256').hexdigest()
    report={'source_parent_job':kept,'source_seconds':60,'source_sha256':fingerprint,
            'transcription_reused':True,'cohort':'approved-style-gpu-v1','models':[]}
    active=[]; paused=False; created_network=False
    try:
        paused=True
        run('docker','stop','content-factory-worker-1','content-factory-kepler-engine-1')
        run('docker','network','create',network);created_network=True
        for tag,filename in [('qwen2.5:1.5b','qwen2.5-1.5b-instruct-q4_k_m.gguf'),
                              ('qwen2.5:3b','qwen2.5-3b-instruct-q4_k_m.gguf')]:
            engine='cf-style-engine-'+suffix; bridge='cf-style-bridge-'+suffix
            print('Loading GPU',tag,flush=True)
            with (models/filename).open('rb') as handle:
                model_hash=hashlib.file_digest(handle,'sha256').hexdigest()
            loaded=time.monotonic()
            run('docker','run','-d','--name',engine,'--network',network,'--network-alias','kepler-engine',
                '--gpus','all','-v','cf_kepler_b4300:/build:ro','-v',str(models)+':/pilot-models:ro',
                '-e','LD_LIBRARY_PATH=/build/bin:/usr/local/cuda-10.2/lib64','--entrypoint','/build/bin/llama-server',
                'content-factory-kepler-lab:cuda10.2','-m','/pilot-models/'+filename,'--host','0.0.0.0','--port','8080',
                '--ctx-size','4096','--batch-size','512','--ubatch-size','256','--gpu-layers','99','--threads','4')
            active.append(engine)
            run('docker','run','-d','--name',bridge,'--network',network,'--network-alias','kepler-bridge',
                '-p','127.0.0.1::11434','-v',str(root/'app/kepler_bridge.py')+':/opt/kepler_bridge.py:ro',
                '-e','KEPLER_MODEL='+tag,'-e','KEPLER_ENGINE_URL=http://kepler-engine:8080',
                '-e','KEPLER_REQUEST_TIMEOUT=300','--entrypoint','python','content-factory-worker:latest',
                '/opt/kepler_bridge.py','bridge')
            active.append(bridge)
            bridge_port=int(run('docker','port',bridge,'11434/tcp').rsplit(':',1)[1])
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{bridge_port}/health',timeout=3) as response:
                        health=json.load(response)
                    if health.get('ok') is True or health.get('status') in ('ok','healthy'):
                        break
                except (OSError,ValueError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError('GPU server unavailable: '+run('docker','logs',engine)[-1500:])
            payload={'source':'/data/input/'+excerpt,'segments':segments,'language':transcript['language'],
                     'model':tag,'model_hash':model_hash,'fingerprint':fingerprint,'parent':kept}
            code="""import json,sys; from pathlib import Path
from app.store import new_job,save,JOBS,load
from app.worker import process
p=json.loads(sys.argv[1])
settings={'clip_count':1,'target_seconds':22,'min_seconds':15,'max_seconds':35,'proposal_max_chunks':1,'shortlist':3,
          'ollama_timeout':300,'whisper_model':'base','ranker_mode':'ollama','llm_backend':'kepler_gpu',
          'llm_model':p['model'],'director_mode':'ollama','render_engine':'remotion','render_quality':'high'}
j=new_job(Path(p['source']),'Comparação GPU '+p['model']+' - referência aprovada (60s).mp4','Ensaio controlado GPU K4200',
          'Usuário autorizou comparação curta da fonte do job aprovado '+p['parent'],settings=settings)
j.update(source_fingerprint=p['fingerprint'],source_parent_job=p['parent'],pipeline_version='approved-style-v2',
         model_artifact_sha256=p['model_hash'],evaluation={'cohort':'approved-style-gpu-v1','variant':p['model']})
save(j)
(JOBS/(j['id']+'.transcript.json')).write_text(json.dumps({'language':p['language'],'segments':p['segments']},ensure_ascii=False),encoding='utf-8')
print('PILOT_JOB '+j['id'],flush=True)
process(j['id'])
print('PILOT_RESULT '+json.dumps(load(j['id']),ensure_ascii=False),flush=True)
"""
            output=run('docker','run','--rm','--network',network,'-v',str(data)+':/data',
                       '-v',str(root/'app')+':/app/app:ro','-e','DATA_DIR=/data',
                       '-e','KEPLER_BRIDGE_URL=http://kepler-bridge:11434','-e','RENDER_TIMEOUT=900',
                       '--entrypoint','python','content-factory-worker:latest','-c',code,json.dumps(payload))
            line=next(v for v in output.splitlines() if v.startswith('PILOT_RESULT '))
            job=json.loads(line[len('PILOT_RESULT '):])
            item={'model':tag,'filename':filename,'model_sha256':model_hash,'job_id':job['id'],'status':job['status'],
                  'ranker_used':job.get('ranker_used'),'seconds_including_load':round(time.monotonic()-loaded,3),
                  'gpu_memory_sample':run('nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader'),
                  'candidates':[{k:c.get(k) for k in ('start','end','state','director_used','renderer_used','word_count')}
                                for c in job['candidates']], 'error':job.get('error')}
            item['passed']=job['status']=='NEEDS_REVIEW' and job.get('ranker_used')=='kepler_gpu' and all(
                c.get('director_used')=='kepler_gpu' and c.get('renderer_used')=='remotion' for c in job['candidates'])
            report['models'].append(item)
            (root/'research/sprint'/('gpu-engine-'+tag.split(':')[-1]+'.log')).write_text(
                run('docker','logs',engine),encoding='utf-8')
            for name in reversed(active):run('docker','rm','-f',name)
            active=[]
            print(json.dumps(item,ensure_ascii=False),flush=True)
    finally:
        for name in reversed(active):
            subprocess.run(['docker','rm','-f',name],capture_output=True)
        if created_network:subprocess.run(['docker','network','rm',network],capture_output=True)
        if paused:
            run('docker','start','content-factory-kepler-engine-1')
            for _ in range(180):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:11436/health',timeout=3) as response:
                        if json.load(response).get('status')=='ok':break
                except (OSError,ValueError):pass
                time.sleep(1)
            run('docker','start','content-factory-worker-1')
        report['approved_reference_unchanged']=before==hashlib.sha256((data/'work'/(kept+'.json')).read_bytes()).hexdigest()
        report['production_restored']=paused
        (root/'research/sprint/approved-style-gpu-pilot.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Production GPU and worker restored',flush=True)


if __name__=='__main__':main()
