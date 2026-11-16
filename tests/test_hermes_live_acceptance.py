"""Opt-in integration test; a separate controller supplies a real Hermes reply."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest
from test_hermes_api import hermes_server
from test_source_ingestion import setup
from test_hermes_reprocess import Queue


@pytest.mark.skipif(not os.getenv('CF_HERMES_LIVE_DIR'), reason='requires explicit live Hermes controller')
def test_live_hermes_plan_reaches_real_render(setup, hermes_server, monkeypatch, tmp_path):
    from app import store, worker, hermes_api
    from app.editorial_requests import prepare_waiting_request, reconcile_accepted_plan

    exchange = Path(os.environ['CF_HERMES_LIVE_DIR'])
    exchange.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parents[1] / 'integrations/hermes/nopocket-content/skills/content-editorial/scripts/editorial_runner.py'
    spec=importlib.util.spec_from_file_location('live_editorial_runner',script)
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    monkeypatch.setattr(hermes_api,'_require_external',lambda _:None)
    monkeypatch.setattr(hermes_api,'_external_allowed',lambda _:True)
    monkeypatch.setattr('app.source_ingestion.require_active_source',lambda _:None)
    monkeypatch.setattr('app.source_registry.get_source',lambda _: {'status':'active'})
    source=tmp_path/'synthetic.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=256x144:rate=30',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','10',
                    '-c:v','libx264','-c:a','aac',str(source)],check=True)
    tx={'language':'pt','segments':[{'start':0.,'end':10.,'text':'O jogo será lançado no próximo ano e o preço oficial ainda não foi confirmado.','words':[]}]}
    job=store.new_job(source,'synthetic','owner','synthetic grant',settings={'editorial_protocol':2,'editorial_planner':'hermes_first','duration_mode':'flexible','min_seconds':8,'target_seconds':10,'max_seconds':30,'clip_count':1,'render_quality':'high'})
    job.update(status='TRANSCRIBING',run_started_at=time.time(),source_snapshot={'channel_id':'synthetic','allowed_model_scopes':['external','local']},
               source_fingerprint=hashlib.sha256(source.read_bytes()).hexdigest(),
               processing_runs=[{'run_id':str(uuid.uuid4()),'state':'RUNNING','started_at':time.time()}])
    row=prepare_waiting_request(job,tx,10.,job['settings'],now=time.time(),timeout=600)
    store.save(job);(store.JOBS/(job['id']+'.transcript.json')).write_text(json.dumps(tx),encoding='utf8')
    def api(method,path,body=None):
        status,result=hermes_server('/v2/hermes'+path,body if method=='POST' else None)
        assert status==200,(status,result)
        return result
    def invoke(view):
        (exchange/'request.json').write_text(json.dumps(view,ensure_ascii=False),encoding='utf8')
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if (exchange/'response.json').is_file():
                return json.loads((exchange/'response.json').read_text(encoding='utf-8-sig'))
            time.sleep(.5)
        raise TimeoutError('Live Hermes response was not supplied')
    pending=runner.PendingSubmission(tmp_path/'pending.json')
    receipt=runner.process_request(job['id'],row['request_id'],api=api,invoke=invoke,
        load_pending=pending.load,save_pending=pending.save,clear_pending=pending.clear)
    assert receipt['state']=='ACCEPTED'
    q=Queue();reconcile_accepted_plan(job['id'],queue=q);assert q.ids==[job['id']]
    monkeypatch.setattr(worker,'JOBS',store.JOBS)
    worker.process(job['id'])
    saved=store.load(job['id'])
    assert saved['status']=='NEEDS_REVIEW', saved.get('error')
    clip=saved['candidates'][0]
    assert clip['proposal_source']=='hermes' and clip['director_used']=='hermes' and clip['renderer_used']=='remotion'
    for path in (Path(clip['file']),Path(clip['file']).with_suffix('.preview.webm')):
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-f','null','-'],check=True)
