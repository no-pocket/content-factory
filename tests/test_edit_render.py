import json
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
    monkeypatch.setenv('RENDER_ENGINE', 'ffmpeg')
    source = tmp_path / 'video.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=256x144:rate=15',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','4','-c:v','libx264','-c:a','aac',str(source)], check=True)
    segments = [{'start': .5, 'end': 2, 'text': 'GTA VI é incrível', 'words': [{'start': .5, 'end': .9, 'text': 'GTA'}, {'start': 1, 'end': 1.3, 'text': 'VI'}]}]
    clip = {'start': 0.2, 'end': 3.2, 'text': 'GTA VI é incrível'}
    timeline = build_timeline(clip, segments)
    target = tmp_path / 'rendered.mp4'
    result = edit_render.render_edited(source, 'jobtest', 1, clip, segments, timeline, {}, target)
    assert result == 'ffmpeg_subtitled'
    assert target.stat().st_size > 1000
    assert target.with_suffix('.timeline.json').exists()
    assert 2.6 < get_duration(target) < 3.4
