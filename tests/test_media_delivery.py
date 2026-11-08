import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.media_delivery import get_delivery_metadata


def probe(monkeypatch, streams, duration='42.867'):
    monkeypatch.setattr('app.media_delivery.subprocess.run', lambda *a, **k: SimpleNamespace(stdout=json.dumps({'streams':streams,'format':{'duration':duration}})))


def video(**kw):
    return dict(codec_type='video',codec_name='h264',width=720,height=1280,sample_aspect_ratio='1:1',**kw)


def test_portrait_delivery_uses_encoded_geometry_and_rounded_duration(monkeypatch, tmp_path):
    probe(monkeypatch,[video(),{'codec_type':'audio','codec_name':'aac'}])
    path = tmp_path / 'master.mp4'
    path.write_bytes(b'\x00\x00\x00\x08moov\x00\x00\x00\x08mdat')
    assert get_delivery_metadata(path) == {'width':720,'height':1280,'duration':43,'supports_streaming':True}


@pytest.mark.parametrize('stream',[video(side_data_list=[{'rotation':90}]),dict(video(),sample_aspect_ratio='16:9'),dict(video(),width=0)])
def test_rejects_ambiguous_geometry(monkeypatch,stream):
    probe(monkeypatch,[stream])
    with pytest.raises(ValueError): get_delivery_metadata(Path('master.mp4'))


@pytest.mark.parametrize('duration',['nan','inf','0','-1'])
def test_rejects_invalid_duration(monkeypatch,duration):
    probe(monkeypatch,[video()],duration)
    with pytest.raises(ValueError): get_delivery_metadata(Path('master.mp4'))



@pytest.mark.parametrize('atoms,expected',[(b'\x00\x00\x00\x08mdat\x00\x00\x00\x08moov',False),(b'\x00\x00\x00\x08moov',True),(b'\x00\x00\x00\x30moov',False)])
def test_streaming_flag_checks_atom_order(monkeypatch,tmp_path,atoms,expected):
    probe(monkeypatch,[video()])
    path=tmp_path/'master.mp4'
    path.write_bytes(atoms)
    assert get_delivery_metadata(path)['supports_streaming'] is expected


@pytest.mark.parametrize('scheduled',[False,True])
def test_render_preserves_synthetic_flash_beep_alignment(tmp_path,scheduled):
    """A shared reference event detects an A/V shift; durations alone cannot."""
    import shutil
    import subprocess
    import numpy as np
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required for signal alignment integration')
    from app.core import render
    source=tmp_path/'reference.mp4'
    target=tmp_path/'render.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
        "color=black:size=160x90:rate=60:duration=3,drawbox=color=white:t=fill:enable='between(t,1,1.15)'",
        '-f','lavfi','-i',"aevalsrc=if(between(t\\,1\\,1.15)\\,0.8*sin(2*PI*1000*t)\\,0):s=48000:d=3",
        '-c:v','libx264','-c:a','aac','-shortest',str(source)],check=True,capture_output=True)
    schedule=[{'start':0,'end':2,'framing':{'preset':'web','roi':{'x':0,'y':0,'width':1,'height':1}}}] if scheduled else None
    render(source,.37,2.37,[],target,width=90,height=160,burn_subtitles=False,framing_schedule=schedule)
    pixels=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(target),
        '-vf','scale=1:1,format=gray','-an','-f','rawvideo','-']),np.uint8)
    audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(target),
        '-vn','-ac','1','-ar','48000','-f','f32le','-']),np.float32)
    flash=np.flatnonzero(pixels>(int(pixels.min())+int(pixels.max()))/2)[0]/30
    beep=np.flatnonzero(np.abs(audio)>.3)[0]/48000
    assert abs(flash-beep)<1/30
    assert abs(beep-(1-.37))<.025
