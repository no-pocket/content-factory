import json
import shutil
import subprocess
from pathlib import Path
from app import edit_render


def test_catalog_rejects_traversal_and_unlicensed(monkeypatch, tmp_path):
    monkeypatch.setattr(edit_render, 'ASSETS_ROOT', tmp_path)
    (tmp_path / 'allowed.mp4').write_bytes(b'fixture')
    (tmp_path / 'catalog.json').write_text(json.dumps({'assets': [
        {'asset_id': 'good', 'file': 'allowed.mp4', 'license_note': 'written grant', 'duration': 12},
        {'asset_id': 'bad', 'file': '../secret.mp4', 'license_note': 'x', 'duration': 12},
        {'asset_id': 'notLicensed', 'file': 'allowed.mp4', 'duration': 12}]}))
    assert list(edit_render.read_assets()) == ['good']


def test_ffmpeg_renderer_fallback_synthetic(tmp_path, monkeypatch):
    import subprocess
    import shutil
    from app.core import get_duration
    from app.timeline import build_timeline
    from app import edit_render
    if not shutil.which('ffmpeg'):
        return
    monkeypatch.setattr(edit_render, 'PUBLIC', tmp_path / 'public')
    monkeypatch.setenv('RENDER_ENGINE', 'remotion')
    source = tmp_path / 'video.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=256x144:rate=15',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','4','-c:v','libx264','-c:a','aac',str(source)], check=True)
    segments = [{'start': .5, 'end': 2, 'text': 'GTA VI é incrível', 'words': [{'start': .5, 'end': .9, 'text': 'GTA'}, {'start': 1, 'end': 1.3, 'text': 'VI'}]}]
    clip = {'start': 0.2, 'end': 3.2, 'text': 'GTA VI é incrível'}
    timeline = build_timeline(clip, segments)
    target = tmp_path / 'rendered.mp4'
    result = edit_render.render_edited(source, 'jobtest', 1, clip, segments, timeline, {}, target,
                                       engine='ffmpeg')
    assert result == 'ffmpeg_subtitled'
    assert target.stat().st_size > 1000
    assert target.with_suffix('.preview.webm').stat().st_size > 1000
    assert target.with_suffix('.timeline.json').exists()
    assert 2.6 < get_duration(target) < 3.4


def test_browser_preview_uses_vp8_opus_and_decodes(tmp_path):
    if not shutil.which('ffmpeg'):
        return
    source = tmp_path / 'candidate.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'testsrc2=size=256x144:rate=15', '-f', 'lavfi',
                    '-i', 'sine=frequency=440:sample_rate=48000', '-t', '2',
                    '-c:v', 'libx264', '-profile:v', 'high', '-c:a', 'aac', str(source)], check=True)
    preview = edit_render.make_web_preview(source)
    assert preview == source.with_suffix('.preview.webm')
    streams = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                                  '-of', 'json', str(preview)]))['streams']
    assert [(s['codec_type'], s['codec_name']) for s in streams] == [('video', 'vp8'), ('audio', 'opus')]
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(preview), '-f', 'null', '-'], check=True)
    assert edit_render.browser_preview(source) == (preview, 'video/webm')
    preview.unlink()
    assert edit_render.browser_preview(source) == (source, 'video/mp4')


def test_high_fidelity_preview_keeps_master_resolution(tmp_path):
    if not shutil.which('ffmpeg'):
        return
    source=tmp_path/'portrait.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=720x1280:rate=10',
                    '-f','lavfi','-i','sine=frequency=440','-t','1','-c:v','libx264','-c:a','aac',str(source)],check=True)
    preview=edit_render.make_web_preview(source,quality='high')
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(preview)]))['streams']
    assert (streams[0]['width'],streams[0]['height'])==(720,1280)


def test_web_framing_preserves_both_source_edges(tmp_path):
    from app.core import render
    from app.framing import validate_framing
    if not shutil.which('ffmpeg'):
        return
    source = tmp_path/'page.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                    'color=white:size=640x360:rate=30:duration=1,drawbox=x=0:y=0:w=30:h=360:color=red:t=fill,drawbox=x=610:y=0:w=30:h=360:color=blue:t=fill',
                    '-c:v','libx264',str(source)],check=True)
    target = tmp_path/'framed.mp4'
    framing = validate_framing({'preset':'web'}, (640,360), (720,1280))
    render(source, 0, 1, [], target, burn_subtitles=False, framing=framing)
    for x, channel in ((10,0),(700,2)):
        raw = subprocess.check_output(['ffmpeg','-v','error','-i',str(target),'-frames:v','1',
                                       '-vf',f'crop=2:2:{x}:440,scale=1:1','-pix_fmt','rgb24','-f','rawvideo','-'])
        assert raw[channel] > 180 and raw[1] < 80


def test_proof_window_adapts_pixels_without_changing_audio_clock(tmp_path):
    from app.core import render, get_duration
    from app.framing import validate_framing_schedule
    source=tmp_path/'page-window.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
        'color=white:size=640x360:rate=30:duration=2,drawbox=x=0:y=0:w=30:h=360:color=red:t=fill,drawbox=x=610:y=0:w=30:h=360:color=blue:t=fill',
        '-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-c:a','aac','-shortest',str(source)],check=True)
    schedule=validate_framing_schedule([{'start':.5,'end':1.5,'framing':{'preset':'web','layout_version':'proof_compact_v2'}}],2,(640,360))
    target=tmp_path/'windowed.mp4'
    render(source,0,2,[],target,burn_subtitles=False,framing_schedule=schedule)
    for moment,protected in ((.25,False),(1,True),(1.75,False)):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(moment),'-i',str(target),'-frames:v','1',
            '-vf','crop=2:2:10:600,scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'])
        if protected:assert raw[0]>180 and raw[1]<80
        else:assert min(raw)>180
    assert abs(get_duration(target)-2)<=1/30
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(target)]))['streams']
    assert sum(s['codec_type']=='audio' for s in streams)==1


def test_finishing_preserves_spoken_audio_then_adds_fading_tail(tmp_path):
    from app.core import get_duration
    from app.edit_render import apply_finishing
    if not shutil.which('ffmpeg'):
        return
    source = tmp_path/'ending.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=white:size=90x160:rate=30',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','1',
                    '-c:v','libx264','-c:a','aac',str(source)],check=True)
    apply_finishing(source, {'duration':1,'finishing':{'tail_seconds':.35,'fade_seconds':.25}}, quality='high')
    assert 1.33 < get_duration(source) < 1.40
    # The source's last spoken interval remains audible; the appended tail is silent.
    import array
    def rms(start):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-i',str(source),'-t','0.06',
                                     '-vn','-ac','1','-f','s16le','-'])
        samples=array.array('h',raw)
        return (sum(v*v for v in samples)/len(samples))**.5
    assert rms(.92) > 500 and rms(1.18) < 40
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss','1.30','-i',str(source),'-frames:v','1',
                                 '-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'])
    assert max(raw) < 70
