"""Objective media checks and contextual signals. No editorial verdicts."""
from __future__ import annotations

import json
import math
import re
import subprocess
import time
from pathlib import Path

QC_DEFAULTS = {
    'duration_tolerance': 0.5, 'silence_db': -40.0, 'silence_seconds': 1.0,
    'black_seconds': 0.5, 'black_pixel_threshold': 0.10,
    'black_picture_ratio': 0.98, 'timeout_seconds': 300, 'max_attempts': 2,
}


def normalize_qc(value: dict | None = None) -> dict:
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value) - set(QC_DEFAULTS):
        raise ValueError('Unknown QC settings')
    result = {**QC_DEFAULTS, **value}
    bounds = {'duration_tolerance': (0.05, 2), 'silence_db': (-90, -10),
              'silence_seconds': (0.1, 30), 'black_seconds': (0.1, 30),
              'black_pixel_threshold': (0, 1), 'black_picture_ratio': (0.5, 1),
              'timeout_seconds': (10, 1800), 'max_attempts': (1, 5)}
    for key, (low, high) in bounds.items():
        x = result[key]
        if type(x) not in (float, int) or not math.isfinite(x) or not low <= x <= high:
            raise ValueError(f'Invalid QC limit: {key}')
    for key in ('max_attempts', 'timeout_seconds'):
        if type(result[key]) is not int:
            raise ValueError(f'{key} must be integer')
    return result


def _probe(path: Path, timeout: int) -> dict:
    cp = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                         '-of', 'json', str(path)], capture_output=True, text=True,
                        check=True, timeout=timeout)
    return json.loads(cp.stdout)


def expects_audio(path: Path) -> bool:
    return any(s.get('codec_type') == 'audio' for s in _probe(path, 30)['streams'])


def inspect_media(path: Path, expected_duration: float, resolution: tuple[int, int],
                  audio_expected: bool, limits: dict) -> dict:
    limits = normalize_qc(limits)
    result = {'state': 'FAILED', 'errors': [], 'warnings': [], 'measurements': {},
              'checked_at': time.time(), 'path': str(path)}
    errors, warnings, measurements = result['errors'], result['warnings'], result['measurements']
    try:
        probe = _probe(path, limits['timeout_seconds'])
        videos = [s for s in probe['streams'] if s.get('codec_type') == 'video']
        audios = [s for s in probe['streams'] if s.get('codec_type') == 'audio']
        duration = float(probe['format']['duration'])
        measurements.update(duration=duration, audio_streams=len(audios), bytes=path.stat().st_size)
        if not math.isfinite(duration) or abs(duration - expected_duration) > limits['duration_tolerance']:
            errors.append('duration_mismatch')
        if not videos:
            errors.append('video_missing')
        else:
            size = (videos[0]['width'], videos[0]['height'])
            measurements['resolution'] = list(size)
            if size != resolution:
                errors.append('resolution_mismatch')
        if audio_expected and not audios:
            errors.append('audio_missing')
        for audio in audios:
            if int(audio.get('sample_rate', 0)) <= 0 or int(audio.get('channels', 0)) <= 0:
                errors.append('audio_invalid')
            if 'duration' in audio and abs(float(audio['duration']) - duration) > limits['duration_tolerance']:
                errors.append('audio_duration_mismatch')
        # -xerror makes corrupt packets a failure. Map all streams of interest.
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'info', '-xerror', '-i', str(path),
               '-map', '0:v?', '-map', '0:a?']
        if videos:
            cmd += ['-vf', f"blackdetect=d={limits['black_seconds']}:pix_th={limits['black_pixel_threshold']}:pic_th={limits['black_picture_ratio']}"]
        if audios:
            cmd += ['-af', f"silencedetect=noise={limits['silence_db']}dB:d={limits['silence_seconds']}"]
        cp = subprocess.run(cmd + ['-f', 'null', '-'], capture_output=True, text=True,
                            timeout=limits['timeout_seconds'], check=True)
        measurements['decoded_complete'] = True
        measurements['black'] = [dict(start=float(a), end=float(b), duration=float(c)) for a, b, c in
                                 re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)', cp.stderr)]
        starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', cp.stderr)]
        ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', cp.stderr)]
        measurements['silence'] = [{'start': a, 'end': ends[i] if i < len(ends) else duration}
                                   for i, a in enumerate(starts)]
        if measurements['black']:
            warnings.append('black_intervals_context_required')
        if measurements['silence']:
            warnings.append('silence_intervals_context_required')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        errors.append('probe_or_decode_failed')
        result['diagnostic'] = (str(exc) + '\n' + str(getattr(exc, 'stderr', '') or '')[-1500:])[:2000]
    result['state'] = 'FAILED' if errors else ('WARNING' if warnings else 'VALID')
    return result


def inspect_candidate(master: Path, duration: float, audio_expected: bool, limits: dict, preview_resolution: tuple[int, int] = (540, 960)) -> dict:
    files = {'mp4': inspect_media(master, duration, (720, 1280), audio_expected, limits),
             'webm': inspect_media(master.with_suffix('.preview.webm'), duration, preview_resolution, audio_expected, limits)}
    states = [f['state'] for f in files.values()]
    return {'version': 1, 'state': 'FAILED' if 'FAILED' in states else ('WARNING' if 'WARNING' in states else 'VALID'),
            'limits': dict(limits), 'files': files}
