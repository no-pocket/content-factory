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
    import array
    import math
    def samples(at):
        raw = subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(target),
            '-t','1','-vn','-ac','1','-ar','8000','-f','s16le','-'])
        values=array.array('h'); values.frombytes(raw)
        return values
    speech=samples(.3)
    crossings=sum(a < 0 <= b for a,b in zip(speech,speech[1:]))
    assert crossings == pytest.approx(600,abs=3)
    assert math.sqrt(sum(v*v for v in speech)/len(speech)) > 1000
    if not audio:
        silence=samples(2.5)
        assert math.sqrt(sum(v*v for v in silence)/len(silence)) < 20
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

@pytest.mark.parametrize('source',[
    'Eu expliquei que vender carros n\u00e3o faz voc\u00ea ganhar dinheiro.',
    'Talvez vender carros possa fazer ganhar dinheiro.',
    'Selling cars might earn money but this is uncertain.',
])
def test_title_does_not_drop_source_polarity_or_uncertainty(source):
    title = 'How to earn money selling cars' if source.startswith('Selling') else 'Como ganhar dinheiro vendendo carros'
    assert not validate_title(title, {'text':source})['valid']

def test_outro_job_freezes_identity_at_submission(tmp_path, monkeypatch):
    import app.store as store
    import app.edit_render as rendering
    monkeypatch.setattr(store, 'save', lambda job: None)
    monkeypatch.setattr(rendering, 'ASSETS_ROOT', tmp_path)
    path=tmp_path/'owner.mp4'; path.write_bytes(b'authorized bytes')
    assets={'asset_owner':{'path':path,'duration':3,'description':'owner ending','license_note':'owner proof'}}
    monkeypatch.setattr(rendering,'read_assets',lambda: assets)
    monkeypatch.setattr('app.core.get_duration', lambda path: 3.0)
    job=store.new_job(None,'source.mp4','owner','proof',settings={'outro_asset_id':'asset_owner'})
    assert job['outro_snapshot']['asset_id']=='asset_owner'
    assert len(job['outro_snapshot']['sha256'])==64
    from app.outro import validate_job_outro
    validate_job_outro(job, assets)
    assets['asset_owner']['license_note']='different proof'
    with pytest.raises(ValueError, match='identity changed'):
        validate_job_outro(job, assets)
    assets['asset_owner']['license_note']='owner proof'
    path.write_bytes(b'replaced authorized bytes')
    with pytest.raises(ValueError, match='identity changed'):
        validate_job_outro(job, assets)
    with pytest.raises(ValueError, match='snapshot'):
        validate_job_outro({'settings':{'outro_asset_id':'asset_owner'}}, assets)

def test_all_candidates_enforce_submission_identity(tmp_path, monkeypatch):
    from pathlib import Path
    from app import candidates, edit_render
    from app.outro import snapshot_outro
    monkeypatch.setattr(edit_render,'ASSETS_ROOT',tmp_path)
    path=tmp_path/'outro.mp4'; path.write_bytes(b'original')
    assets={'owner':{'path':path,'license_note':'proof','description':'ending','duration':2}}
    monkeypatch.setattr('app.core.get_duration',lambda path: 2.0)
    frozen=snapshot_outro('owner',assets)
    monkeypatch.setattr(candidates,'OUTPUT',tmp_path)
    monkeypatch.setattr(candidates,'save',lambda job: None)
    monkeypatch.setattr(candidates,'read_assets',lambda: assets)
    monkeypatch.setattr(candidates,'direct_edit',lambda *a,**k: ({},'heuristic'))
    monkeypatch.setattr(candidates,'build_timeline',lambda *a,**k: {'layers':{'captions':[]}})
    monkeypatch.setattr(candidates,'inspect_candidate',lambda *a: {'state':'VALID'})
    calls=[]
    def render(*args,**kwargs):
        calls.append(kwargs['outro_snapshot'])
        assert kwargs['outro_snapshot']==frozen
        path.write_bytes(b'changed after first candidate')
        return 'test'
    monkeypatch.setattr(candidates,'render_edited',render)
    job={'id':'test','outro_snapshot':frozen,'candidates':[{'start':0,'end':10},{'start':10,'end':20}]}
    candidates.render_candidates(job,Path('source'),[],{'outro_asset_id':'owner'},True)
    assert len(calls)==1
    assert job['candidates'][1]['state']=='FAILED'
    assert 'identity changed' in job['candidates'][1]['attempt_history'][0]['error']
    candidates.render_candidates(job,Path('source'),[],{'outro_asset_id':'owner'},True,only=1)
    assert len(calls)==1
    assert 'identity changed' in job['candidates'][1]['attempt_history'][1]['error']

@pytest.mark.parametrize('title,source', [
    ('Como ganhar dinheiro comprando barcos','Para ganhar dinheiro voc\u00ea deve vender carros. Comprar barcos faz perder dinheiro.'),
    ('Alice venceu Bruno','Bruno venceu Alice durante a corrida.'),
    ('Carros compram jogadores','Jogadores compram carros depois da corrida.'),
])
def test_title_rejects_relation_swap_or_cross_clause_synthesis(title, source):
    assert not validate_title(title, {'text':source})['valid']

def test_title_accepts_ordered_single_clause_paraphrase():
    assert validate_title('Como ganhar dinheiro vendendo carros', {'text':'O segredo para ganhar dinheiro consiste em vender carros.'})['valid']

@pytest.mark.parametrize('source', [
    'Para ganhar dinheiro deve vender carros antes de comprar barcos.',
    'Para ganhar dinheiro deve vender carros e comprar barcos faz perder dinheiro.',
])
def test_title_cannot_skip_an_intervening_action_to_reassign_result(source):
    result=validate_title('Como ganhar dinheiro comprando barcos', {'text':source})
    assert not result['valid']
    assert result['reason']=='unsupported_title_relation'
