"""Smoke test render without YouTube, Redis, Whisper or Ollama.

Run inside worker: python -m app.demo_render
"""
from __future__ import annotations
import os
import subprocess
import uuid
from pathlib import Path
from .core import get_duration
from .edit_render import render_edited
from .timeline import build_timeline


def main():
    destination = Path(os.getenv('DATA_DIR', 'data')) / 'demo'
    destination.mkdir(parents=True, exist_ok=True)
    source = destination / 'source.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=25',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '7',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', str(source)], check=True)
    words = [
        {'start': .4, 'end': .8, 'text': 'Esse'},
        {'start': .9, 'end': 1.4, 'text': 'detalhe'},
        {'start': 1.5, 'end': 1.8, 'text': 'do'},
        {'start': 1.9, 'end': 2.4, 'text': 'GTA'},
        {'start': 2.5, 'end': 3.0, 'text': 'VI'},
        {'start': 3.1, 'end': 3.7, 'text': 'é'},
        {'start': 3.8, 'end': 4.4, 'text': 'incrível'},
    ]
    segments = [{'start': .4, 'end': 4.4, 'text': 'Esse detalhe do GTA VI é incrível', 'words': words}]
    clip = {'start': 0, 'end': 6, 'text': 'Esse detalhe do GTA VI é incrível'}
    timeline = build_timeline(clip, segments, edit={'hook': 'Esse detalhe do GTA VI', 'effects': [{'type': 'punch_zoom', 'at': 3}], 'broll': []})
    target = destination / 'demo.mp4'
    used = render_edited(source, str(uuid.uuid4()), 1, clip, segments, timeline, {}, target)
    print(f'RENDER_ENGINE_USED={used}')
    print(f'VIDEO={target} DURATION={get_duration(target):.2f}s')
    print(f'TIMELINE={target.with_suffix(".timeline.json")}')
    if os.getenv('RENDER_ENGINE', 'remotion') == 'remotion' and used != 'remotion':
        raise RuntimeError('Remotion smoke test fell back; inspect logs and Docker image')

if __name__ == '__main__':
    main()
