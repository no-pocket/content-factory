"""Offline signal experiments. These observations never silently change ranking."""
from __future__ import annotations

import copy
import math
import re
import subprocess
import time
from pathlib import Path


def parse_signals(log: str) -> dict:
    result = {'silence': [], 'energy': [], 'scenes': []}
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', log)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', log)]
    result['silence'] = [{'start': a, 'end': ends[i]} for i, a in enumerate(starts) if i < len(ends)]
    at = 0.0
    for line in log.splitlines():
        stamp = re.search(r'pts_time[:=]([\d.]+)', line)
        if stamp:
            at = float(stamp[1])
        energy = re.search(r'lavfi.astats.Overall.RMS_level=([-\w.]+)', line)
        if energy:
            value = float(energy[1])
            result['energy'].append({'time': at, 'rms_db': value if math.isfinite(value) else None})
        scene = re.search(r'lavfi.scene_score=([\d.]+)', line)
        if scene:
            result['scenes'].append({'time': at, 'score': float(scene[1])})
    return result


def extract_signals(source: Path) -> dict:
    started = time.monotonic()
    # Separate passes keep audio/video metadata clocks unambiguous; constant-memory decode.
    audio = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(source), '-vn',
                            '-af', 'aresample=48000,asetnsamples=n=24000,silencedetect=n=-40dB:d=0.3,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level',
                            '-f', 'null', '-'], capture_output=True, text=True, check=True, timeout=1800)
    audio_seconds = time.monotonic() - started
    video = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(source), '-an',
                            '-vf', "scale=320:-2,select='gt(scene,0.3)',metadata=print:key=lavfi.scene_score",
                            '-fps_mode', 'vfr', '-f', 'null', '-'],
                           capture_output=True, text=True, check=True, timeout=1800)
    result = parse_signals(audio.stderr)
    result['scenes'] = parse_signals(video.stderr)['scenes']
    result.update(version=1, elapsed_seconds=round(time.monotonic() - started, 3),
                  audio_seconds=round(audio_seconds, 3),
                  parameters={'silence_db': -40, 'silence_seconds': 0.3, 'rms_window_seconds': 0.5,
                              'scene_threshold': 0.3, 'scene_width': 320})
    return result


def boundary_experiment(clips: list[dict], signals: dict, duration: float, *,
                        min_seconds: float = 15, max_seconds: float = 60) -> list[dict]:
    adjusted = copy.deepcopy(clips)
    for clip in adjusted:
        before = {'start': clip['start'], 'end': clip['end']}
        # End silence before entering a clip; stop at start of silence when leaving.
        starts = [s['end'] for s in signals['silence']] + [s['time'] for s in signals['scenes']]
        ends = [s['start'] for s in signals['silence']] + [s['time'] for s in signals['scenes']]
        start = min(starts, key=lambda t: abs(t - clip['start']), default=clip['start'])
        end = min(ends, key=lambda t: abs(t - clip['end']), default=clip['end'])
        start = start if abs(start - clip['start']) <= 0.75 else clip['start']
        end = end if abs(end - clip['end']) <= 0.75 else clip['end']
        if 0 <= start < end <= duration and min_seconds <= end - start <= max_seconds:
            clip.update(start=round(start, 3), end=round(end, 3))
        clip.update(experimental=True, baseline_window=before)
    return adjusted
