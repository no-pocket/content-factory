import io
import subprocess
import shutil
import json
from pathlib import Path
import pytest

@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg unavailable')
def test_add_licensed_asset(tmp_path, monkeypatch):
    from app import asset_library
    monkeypatch.setattr(asset_library, 'ROOT', tmp_path)
    source = tmp_path / 'src.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=128x72:rate=12','-t','3','-c:v','mpeg4',str(source)], check=True)
    record = asset_library.register_asset(io.BytesIO(source.read_bytes()), 'a.mp4', 'Carros na rua', 'Autorizado por escrito')
    assert record['duration'] >= 2
    assert (tmp_path/'assets'/record['file']).exists()
    assert len(json.loads((tmp_path/'assets'/'catalog.json').read_text())['assets']) == 1


def test_refuses_missing_license(tmp_path):
    from app import asset_library
    with pytest.raises(ValueError):
        asset_library.register_asset(io.BytesIO(b'data'), 'x.mp4', 'Descrição', '')
