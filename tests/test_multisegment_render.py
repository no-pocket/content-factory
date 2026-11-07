import array
import json
from pathlib import Path
import subprocess

import pytest


def assembly_plan():
    return {'schema_version':'3.0','source_duration':4,'segments':[
        {'segment_id':'setup','source_in':0,'source_out':1,'purpose':'setup'},
        {'segment_id':'payoff','source_in':3,'source_out':4,'purpose':'payoff'}]}


def test_multisegment_timeline_maps_words_and_duration():
    from app.timeline import build_timeline, validate_timeline
    clip={'start':0,'end':4,'text':'Synthetic setup payoff','assembly':assembly_plan()}
    segments=[{'start':0,'end':4,'text':clip['text'],'words':[
        {'start':.1,'end':.4,'text':'setup'}, {'start':3.1,'end':3.4,'text':'payoff'}]}]
    timeline=build_timeline(clip,segments)
    assert timeline['schema_version']=='3.0'
    assert timeline['duration']==2
    assert timeline['layers']['captions'][1]['start']==pytest.approx(1.1)
    assert timeline['layers']['captions'][1]['source_start']==3.1
    validate_timeline(timeline)
    from jsonschema import Draft202012Validator
    schema=json.loads((Path(__file__).parent.parent/'contracts/timeline-v3.schema.json').read_text())
    Draft202012Validator(schema).validate(timeline)


def test_assembly_render_matches_video_audio_markers_within_one_frame(tmp_path):
    from app.assembly import validate_assembly, render_assembly
    source=tmp_path/'markers.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
        r'color=red:size=160x90:rate=30:duration=4,drawbox=x=0:y=0:w=iw:h=ih:color=green:t=fill:enable=gte(t\,3)',
        '-f','lavfi','-i',r'aevalsrc=0.2*sin(2*PI*(440+440*gte(t\,2))*t):s=48000:d=4',
        '-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(source)],check=True)
    target=tmp_path/'assembled.mp4'
    render_assembly(source,validate_assembly(assembly_plan(),4),target,quality='standard')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(target)]))
    assert abs(float(probe['format']['duration'])-2) <= 1/30
    for moment,channel in ((.5,0),(1.5,1)):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(moment),'-i',str(target),'-frames:v','1','-vf','scale=1:1','-pix_fmt','rgb24','-f','rawvideo','-'])
        assert raw[channel]>90 and raw[2]<50
    def frequency_at(start):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-i',str(target),'-t','0.1','-vn','-ac','1','-ar','48000','-f','s16le','-'])
        samples=array.array('h',raw)
        return sum(a<=0<b for a,b in zip(samples,samples[1:]))/.1
    assert 420 <= frequency_at(.4) <= 460
    assert 850 <= frequency_at(1.4) <= 910
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'],check=True)


def test_invalid_plan_rejected_before_ffmpeg(tmp_path, monkeypatch):
    from app.assembly import render_assembly
    def forbidden(*args,**kwargs):
        pytest.fail('Invalid plan reached subprocess')
    monkeypatch.setattr(subprocess,'run',forbidden)
    item=assembly_plan()
    item['segments'][1]['output_start']=2
    with pytest.raises(ValueError):
        render_assembly(Path('synthetic'),item,tmp_path/'no.mp4')


def test_assembly_submission_is_opt_in_and_snapshot_bound(tmp_path,monkeypatch):
    from app import service, store
    monkeypatch.setattr(store,'JOBS',tmp_path)
    queue=type('Queue',(),{'lpush':lambda *args:None})()
    payload={'source_url':'https://youtu.be/dQw4w9WgXcQ','creator':'SYNTHETIC','license_note':'synthetic grant',
             'rights_confirmed':True,'platform_permission':True,'assembly_plan':assembly_plan()}
    with pytest.raises(ValueError,match='timeline_v3'):
        service.create_job(payload,queue=queue)
    job=service.create_job({**payload,'settings':{'timeline_v3':True,'editorial_protocol':2}},queue=queue)
    assert job['assembly_plan']['segments'][1]['output_start']==1
    assert store.load(job['id'])['assembly_plan']==job['assembly_plan']


def test_v3_caption_clock_cannot_disagree_with_source_provenance():
    from app.timeline import build_timeline, validate_timeline
    clip={'start':0,'end':4,'text':'setup payoff','assembly':assembly_plan()}
    timeline=build_timeline(clip,[{'start':0,'end':4,'text':'setup payoff',
        'words':[{'start':3.1,'end':3.4,'text':'payoff'}]}])
    timeline['layers']['captions'][0]['start']+=.05
    with pytest.raises(ValueError):validate_timeline(timeline)
