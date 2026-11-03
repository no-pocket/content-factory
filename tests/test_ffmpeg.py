import shutil
import subprocess
from app.core import render, get_duration
import pytest

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg not installed")
def test_render_synthetic(tmp_path):
    src = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "4", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    dest = tmp_path / "preview.mp4"
    render(src, 0.5, 3.5, [{"start": 1.0, "end": 2.0, "text": "Test subtitle"}], dest, width=270, height=480)
    assert dest.stat().st_size > 1000
    assert 2.5 <= get_duration(dest) <= 3.5
