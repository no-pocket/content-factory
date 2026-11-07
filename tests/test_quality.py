import shutil
import subprocess

import pytest

from app.quality import inspect_media, inspect_candidate, normalize_qc

pytestmark = pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')


def media(path, *, audio=True, black=False):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
           'color=black:size=90x160:rate=10' if black else 'testsrc2=size=90x160:rate=10']
    if audio:
        cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono' if black else 'sine=frequency=440']
    cmd += ['-t', '2', '-c:v', 'libx264']
    if audio:
        cmd += ['-c:a', 'aac']
    subprocess.run(cmd + [str(path)], check=True)


def test_valid_media_and_contextual_warnings(tmp_path):
    path = tmp_path / 'black.mp4'
    media(path, black=True)
    report = inspect_media(path, 2, (90, 160), True, normalize_qc())
    assert report['state'] == 'WARNING'
    assert report['measurements']['silence']
    assert report['measurements']['black']
    assert report['errors'] == []


def test_missing_audio_wrong_dimensions_duration_and_corruption_fail(tmp_path):
    path = tmp_path / 'silent.mp4'
    media(path, audio=False)
    report = inspect_media(path, 5, (720, 1280), True, normalize_qc())
    assert report['state'] == 'FAILED'
    assert {'audio_missing', 'resolution_mismatch', 'duration_mismatch'} <= set(report['errors'])
    path.write_bytes(b'broken')
    assert inspect_media(path, 2, (90, 160), False, normalize_qc())['state'] == 'FAILED'


def test_candidate_requires_both_outputs(tmp_path):
    path = tmp_path / 'candidate.mp4'
    media(path)
    report = inspect_candidate(path, 2, True, normalize_qc())
    assert report['state'] == 'FAILED'
    assert report['files']['webm']['errors']


def test_qc_rejects_unknown_and_invalid_limits():
    with pytest.raises(ValueError):
        normalize_qc({'max_attempts': 0})
    with pytest.raises(ValueError):
        normalize_qc({'black_pixel_threshold': float('nan')})
