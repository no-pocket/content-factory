import pytest
from app.job_settings import normalize_job_settings
from app.editorial_context import validate_title

def test_outro_settings_default_and_validation():
    assert normalize_job_settings({})['outro_asset_id'] is None
    assert normalize_job_settings({'outro_asset_id':'asset_123abc'})['outro_asset_id']=='asset_123abc'
    with pytest.raises(ValueError): normalize_job_settings({'outro_asset_id':'../secret.mp4'})

def test_grounded_paraphrase_title():
    evidence={'text':'O segredo para ganhar dinheiro no GTA é vender os carros depois da missão.'}
    assert validate_title('Como ganhar dinheiro vendendo carros no GTA', evidence)['valid']
    assert not validate_title('Ganhe 500 milhões com carros no GTA',evidence)['valid']
    assert not validate_title('O segredo para ganhar dinheiro',evidence)['valid']

@pytest.mark.parametrize('audio', [True, False])
def test_append_outro_real_av(tmp_path, monkeypatch, audio):
    import shutil
    import subprocess
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required; run in worker image')
    from app.outro import append_outro
    from app.core import get_duration
    from app.quality import expects_audio
    import app.edit_render as edit_render
    monkeypatch.setattr(edit_render, 'ASSETS_ROOT', tmp_path)
    target=tmp_path/'master.mp4'
    outro=tmp_path/'asset.mp4'
    def create(path, color, with_audio):
        args=['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c={color}:s=180x320:r=30:d=2']
        if with_audio:
            args += ['-f','lavfi','-i','sine=frequency=600:duration=2','-c:a','aac']
        subprocess.run(args+['-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True,capture_output=True)
    create(target,'blue',True)
    create(outro,'red',audio)
    result=append_outro(target,'asset_test',{'asset_test':{'path':outro,'license_note':'owner test fixture'}})
    assert abs(get_duration(target)-4)<0.15
    assert expects_audio(target)
    assert result['start']==pytest.approx(2,abs=.05)
    assert len(result['sha256'])==64
    with pytest.raises(ValueError, match='bytes changed'):
        append_outro(target,'asset_test',{'asset_test':{'path':outro,'license_note':'owner test fixture'}},expected_sha256='0'*64)
    # The original speech audio survives the first segment, and the whole file decodes.
    probe=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'],capture_output=True)
    assert probe.returncode==0

def test_outro_rejects_unlicensed_or_escaped_asset(tmp_path):
    from app.outro import append_outro
    with pytest.raises(ValueError):
        append_outro(tmp_path/'master.mp4','../secret',{})
    with pytest.raises(ValueError):
        append_outro(tmp_path/'master.mp4','asset_test',{'asset_test':{'path':tmp_path/'missing.mp4','license_note':''}})


def test_candidate_duration_includes_outro_without_moving_captions():
    from app.timeline import candidate_duration
    clip={'start':5,'end':15,'timeline':{'duration':10,'finishing':{'tail_seconds':.35},
        'outro':{'duration':2},'layers':{'captions':[{'start':0,'end':10,'text':'source'}]}}}
    assert candidate_duration(clip)==12.35
    assert clip['timeline']['layers']['captions'][0]['end']==10
