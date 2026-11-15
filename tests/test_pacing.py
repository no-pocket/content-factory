import copy
import pytest
from app.assembly import validate_assembly, map_words


def test_speed_remaps_frame_clock_and_word_provenance():
    plan=validate_assembly({'schema_version':'3.0','source_duration':30,'segments':[
        {'segment_id':'one','source_in':0,'source_out':11,'purpose':'fala','playback_rate':1.1},
        {'segment_id':'two','source_in':20,'source_out':25,'purpose':'final'}]},30)
    assert plan['segments'][0]['frame_count']==300 and plan['duration']==15
    words=map_words(plan,[{'start':2.2,'end':3.3,'text':'fala'}, {'start':21,'end':22,'text':'final'}])
    assert words[0]['start']==pytest.approx(2) and words[0]['end']==pytest.approx(3)
    assert words[0]['source_start']==2.2 and words[1]['start']==11


@pytest.mark.parametrize('rate',[True,0.9,1.16,float('nan')])
def test_speed_rejects_invalid_or_excessive_acceleration(rate):
    with pytest.raises(ValueError):
        validate_assembly({'schema_version':'3.0','source_duration':10,'segments':[
            {'segment_id':'one','source_in':0,'source_out':10,'purpose':'fala','playback_rate':rate}]},10)


def test_slow_speech_accelerates_without_shortening_below_saved_minimum():
    from app.pacing import pace_plan
    plan={'schema_version':'3.0','source_duration':40,'segments':[
        {'segment_id':'one','source_in':0,'source_out':40,'purpose':'fala'}]}
    segments=[{'words':[{'start':i,'end':i+.6,'text':'fala'} for i in range(40)]}]
    result,diagnostic=pace_plan(plan,segments,min_seconds=8)
    assert diagnostic['rate']==1.15 and result['duration']<40
    natural,_=pace_plan(plan,segments,min_seconds=8,preference='natural')
    assert natural['duration']==40
    minimum,_=pace_plan(plan,segments,min_seconds=40)
    assert minimum['duration']==40
    assert 'duration' not in plan  # no input mutation


def test_actual_ffmpeg_acceleration_preserves_pitch_duration_and_caption_clock(tmp_path):
    import subprocess,json
    import numpy as np
    from app.assembly import render_assembly
    from app.timeline import build_timeline,validate_timeline
    source=tmp_path/'source.mp4'; target=tmp_path/'paced.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=160x90:r=30:d=4',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4',
        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(source)],check=True)
    plan=validate_assembly({'schema_version':'3.0','source_duration':4,'segments':[
        {'segment_id':'one','source_in':0,'source_out':2.2,'purpose':'fala','playback_rate':1.1}]},4)
    render_assembly(source,plan,target)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(target)]))
    assert float(next(s for s in probe['streams'] if s['codec_type']=='video')['duration'])==pytest.approx(2,abs=.04)
    pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(target),'-vn','-ac','1','-ar','48000','-f','f32le','-'])
    signal=np.frombuffer(pcm,dtype=np.float32); signal=signal[len(signal)//4:3*len(signal)//4]
    peak=np.fft.rfftfreq(len(signal),1/48000)[np.argmax(abs(np.fft.rfft(signal)))]
    assert peak==pytest.approx(440,abs=3)
    subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True,capture_output=True)
    timeline=build_timeline({'start':0,'end':2.2,'text':'fala','assembly':plan},
        [{'words':[{'start':.55,'end':1.1,'text':'fala'}]}])
    validate_timeline(timeline)
    assert timeline['layers']['captions'][0]['start']==pytest.approx(.5)


def test_frame_analysis_samples_the_correct_source_in_accelerated_segments():
    from app.frame_analysis import _source_at
    timeline={'schema_version':'3.0','segments':[{'source_in':10,'source_out':21,
        'output_start':0,'duration':10,'playback_rate':1.1}]}
    assert _source_at(timeline,2)==pytest.approx(12.2)
    assert _source_at(timeline,10.1)==21


def test_native_groups_preserve_zero_duration_words_using_observed_bounds_only():
    from app.assembly import native_word_groups,build_assembly_context
    original=[{'start':0,'end':2,'text':'não faça isso','words':[
        {'start':0,'end':0,'text':'não'},{'start':0,'end':1,'text':'faça'}, {'start':1,'end':2,'text':'isso'}]}]
    before=copy.deepcopy(original); grouped=native_word_groups(original)
    assert original==before
    assert grouped[0]['words'][0]['text']=='não faça'
    assert grouped[0]['words'][0]['start']==0 and grouped[0]['words'][0]['end']==1
    assert grouped[0]['words'][0]['source_word_ids']==['0:0','0:1']
    plan={'schema_version':'3.0','source_duration':2,'segments':[
        {'segment_id':'one','source_in':0,'source_out':2,'purpose':'fala original'}]}
    context=build_assembly_context(plan,original)
    assert context['text']=='não faça isso'
    assert context['word_timing_diagnostics']['zero_duration_words_grouped']==1


def test_optional_pacing_keeps_long_contiguous_clips_compatible():
    from app.pacing import apply_candidate_pacing
    clip={'start':0,'end':150,'text':'fala longa'}
    assert apply_candidate_pacing(clip,[],180,{'auto_pace':True,'min_seconds':8})==1
    assert 'assembly' not in clip and clip['pace']['reason']=='contiguous_over_120_seconds'

