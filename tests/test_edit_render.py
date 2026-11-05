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
