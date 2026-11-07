import json
import pytest


def test_stage_metric_keeps_failure_versions_and_config_without_content():
    from app.telemetry import measure_stage
    metrics=[]
    context={'job_id':'synthetic','candidate_id':'candidate','render_revision':2,
             'configuration_sha256':'a'*64,'component_snapshot_id':'b'*64}
    with pytest.raises(ValueError):
        with measure_stage(metrics,'DIRECTOR',context,requested='ollama'):
            raise ValueError('sensitive transcript must not enter metrics')
    metric=metrics[0]
    assert metric['stage']=='DIRECTOR' and metric['state']=='FAILED'
    assert metric['seconds']>=0 and metric['render_revision']==2
    assert metric['component_snapshot_id']=='b'*64
    assert 'sensitive transcript' not in json.dumps(metric)


def test_actual_ffmpeg_render_records_all_render_stages(tmp_path,monkeypatch):
    import subprocess
    from app import edit_render
    from app.timeline import build_timeline
    monkeypatch.setattr(edit_render,'PUBLIC',tmp_path/'public')
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=30:duration=1',
                    '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest',str(source)],check=True)
    clip={'start':0,'end':1,'text':'Synthetic'};timeline=build_timeline(clip,[]);metrics=[]
    result=edit_render.render_edited(source,'metric-fixture',1,clip,[],timeline,{},tmp_path/'master.mp4',
        engine='ffmpeg',metrics=metrics,metric_context={'job_id':'synthetic','render_revision':1,'configuration_sha256':'a'*64,'component_snapshot_id':'b'*64})
    assert result=='ffmpeg_subtitled'
    assert {'BASE','REMOTION','FINISHING','PREVIEW'}<={m['stage'] for m in metrics}
    assert next(m for m in metrics if m['stage']=='REMOTION')['state']=='SKIPPED'
    assert all(m['seconds']>=0 and m['configuration_sha256']=='a'*64 for m in metrics)


def test_high_fidelity_failure_does_not_claim_a_resolved_renderer(tmp_path,monkeypatch):
    import subprocess
    from app import edit_render
    from app.timeline import build_timeline
    original_run=subprocess.run
    monkeypatch.setattr(edit_render,'PUBLIC',tmp_path/'public')
    source=tmp_path/'source.mp4'
    original_run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=30:duration=1',
                  '-c:v','libx264',str(source)],check=True)
    def fail_remotion(args,**kwargs):
        if args[0].endswith('/remotion'):raise subprocess.CalledProcessError(1,args)
        return original_run(args,**kwargs)
    monkeypatch.setattr(subprocess,'run',fail_remotion)
    clip={'start':0,'end':1,'text':'Synthetic'};metrics=[]
    with pytest.raises(subprocess.CalledProcessError):
        edit_render.render_edited(source,'metric-failure',1,clip,[],build_timeline(clip,[]),{},tmp_path/'master.mp4',
                                  engine='remotion',quality='high',metrics=metrics)
    failed=next(m for m in metrics if m['stage']=='REMOTION')
    assert failed['state']=='FAILED' and failed['resolved']=='NONE'
    assert failed['fallback_reason']=='disabled_for_high_fidelity'


def test_snapshot_declares_actual_timeline_opt_in():
    from app.provenance import component_snapshot
    from app.job_settings import normalize_job_settings
    settings=normalize_job_settings({'editorial_protocol':2,'timeline_v3':True})
    assert component_snapshot(settings)['timeline_schema']=='3.0'
