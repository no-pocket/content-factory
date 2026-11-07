"""Controlled synthetic Remotion benchmark: three post-encode and three composed tails.

No source media, models, Redis, external services or human feedback are used.
The output directory must be new. Both arms keep the master and preview.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time

from app.artifacts import digest
from app.edit_render import render_edited
from app.job_settings import normalize_job_settings
from app.provenance import component_snapshot
from app.quality import inspect_candidate, normalize_qc
from app.timeline import build_timeline, output_duration


def cgroup():
    result={}
    for name in ('cpu.max','cpu.stat','memory.current','memory.peak'):
        path=Path('/sys/fs/cgroup')/name
        if path.is_file():result[name]=path.read_text().strip()
    return result


def rms(path: Path, start: float) -> float:
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-i',str(path),'-t','0.06',
                                 '-vn','-ac','1','-ar','48000','-f','s16le','-'])
    samples=array.array('h',raw)
    return (sum(v*v for v in samples)/len(samples))**.5


def ssim(a: Path,b: Path, *, tail=False) -> float:
    prefix='trim=start_frame=60,setpts=PTS-STARTPTS,' if tail else ''
    graph=f'[0:v]{prefix}null[a];[1:v]{prefix}null[b];[a][b]ssim'
    result=subprocess.run(['ffmpeg','-v','info','-i',str(a),'-i',str(b),'-lavfi',graph,'-f','null','-'],
                          check=True,capture_output=True,text=True)
    match=re.search(r'All:([0-9.]+)',result.stderr)
    if not match:raise ValueError('SSIM measurement unavailable')
    return float(match[1])


def run(output: Path) -> dict:
    output.mkdir(parents=True,exist_ok=False)
    source=output/'synthetic-source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
        r'testsrc2=size=640x360:rate=30:duration=4',
        '-f','lavfi','-i',r'aevalsrc=0.2*sin(2*PI*(440+440*gte(t\,2))*t):s=48000:d=4',
        '-c:v','libx264','-preset','veryfast','-c:a','aac','-shortest',str(source)],check=True)
    plan={'schema_version':'3.0','source_duration':4,'segments':[
        {'segment_id':'setup','source_in':0,'source_out':1,'purpose':'Synthetic setup'},
        {'segment_id':'payoff','source_in':3,'source_out':4,'purpose':'Synthetic payoff'}]}
    clip={'start':0,'end':4,'text':'Synthetic setup. Complete payoff.','assembly':plan}
    segments=[{'start':0,'end':1,'text':'Synthetic setup.','words':[
        {'start':.1,'end':.4,'text':'Synthetic'},{'start':.4,'end':.99,'text':'setup.'}]},
        {'start':3,'end':4,'text':'Complete payoff.','words':[
        {'start':3,'end':3.4,'text':'Complete'},{'start':3.4,'end':3.9,'text':'payoff.'}]}]
    settings=normalize_job_settings({'editorial_protocol':2,'timeline_v3':True})
    snapshot=component_snapshot(settings)
    fixed=digest({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'plan':plan,'quality':'high','engine':'remotion'})
    rows=[]
    # One explicit warmup, then the planned three baseline and three candidate runs.
    for index,mode in enumerate(['post_encode']*4+['remotion']*3):
        timeline=build_timeline(clip,segments,edit={'hook':'Complete synthetic payoff','effects':[{'type':'punch_zoom','at':.5}]})
        target=output/f'{index}-{mode}.mp4';metrics=[]
        context={'job_id':'SYNTHETIC-finishing-benchmark','render_revision':index+1,
                 'configuration_sha256':digest({'fixed':fixed,'finishing_mode':mode}),
                 'component_snapshot_id':snapshot['snapshot_id']}
        before=cgroup();started=time.perf_counter()
        used=render_edited(source,'finishing-benchmark',index+1,clip,segments,timeline,{},target,
                          engine='remotion',quality='high',finishing_mode=mode,metrics=metrics,metric_context=context)
        elapsed=time.perf_counter()-started
        qc=inspect_candidate(target,output_duration(timeline),True,normalize_qc(),(720,1280))
        if used!='remotion' or qc['state'] not in ('VALID','WARNING'):
            raise ValueError('Benchmark arm failed Remotion/QC; comparison invalid')
        spoken,tail=rms(target,1.9),rms(target,2.18)
        if spoken<500 or tail>50:raise ValueError('Finishing changed speech or silent tail')
        row={'mode':mode,'warmup':index==0,'wall_seconds':elapsed,'metrics':metrics,'qc':qc,
             'source_and_fixed_options_sha256':fixed,'master':target.name,'preview':target.with_suffix('.preview.webm').name,
             'rms_last_speech':spoken,'rms_tail':tail,'resources_before':before,'resources_after':cgroup()}
        rows.append(row)
        (output/'partial.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps({'run':index,'mode':mode,'seconds':round(elapsed,3),'qc':qc['state']}),flush=True)
    baseline=[r['wall_seconds'] for r in rows if r['mode']=='post_encode' and not r['warmup']]
    candidate=[r['wall_seconds'] for r in rows if r['mode']=='remotion']
    comparisons=[{'full_ssim':ssim(output/a['master'],output/b['master']),
                  'tail_ssim':ssim(output/a['master'],output/b['master'],tail=True)}
                 for a,b in zip(rows[1:4],rows[4:])]
    gain=1-statistics.mean(candidate)/statistics.mean(baseline)
    report={'schema_version':'1.0','synthetic':True,'ai_inference_performed':False,'image_id':os.getenv('CONTENT_FACTORY_IMAGE_ID','UNKNOWN'),
            'component_snapshot':snapshot,'runs':rows,'baseline_seconds':baseline,'candidate_seconds':candidate,
            'baseline_mean':statistics.mean(baseline),'candidate_mean':statistics.mean(candidate),'relative_wall_gain':gain,
            'comparisons':comparisons,'quality_thresholds':{'full_ssim':.98,'tail_ssim':.95,'rms_tail_max':50},
            'synthetic_quality_gate':all(c['full_ssim']>=.98 and c['tail_ssim']>=.95 for c in comparisons),
            'promotion':'NOT_PROMOTED_REQUIRES_HUMAN_REVIEW','limitations':'Three repetitions on one synthetic source; no statistical/editorial generalization.'}
    for name,index,at in [('baseline-body',1,.5),('candidate-body',4,.5),('baseline-tail',1,2.2),('candidate-tail',4,2.2),('candidate-junction',4,1.01)]:
        subprocess.run(['ffmpeg','-v','error','-ss',str(at),'-i',str(output/rows[index]['master']),'-frames:v','1',str(output/(name+'.png'))],check=True)
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    report=run(parser.parse_args().output)
    print(json.dumps({k:report[k] for k in ('baseline_mean','candidate_mean','relative_wall_gain','synthetic_quality_gate','promotion')}))


if __name__=='__main__':main()
