"""Capture exact local replies for a failed proposal sample, without changing prompts."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import urllib.request

from app.ranker import propose_from_transcript
from app.store import JOBS, load
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    job = load(args.job)
    segments = json.loads((JOBS / (args.job + '.transcript.json')).read_text(encoding='utf-8'))['segments'][:12]
    original = urllib.request.urlopen
    rows = []
    for model in ('qwen2.5:1.5b', 'qwen2.5:3b'):
        events, calls = [], []
        def capture(request, *arguments, **kwargs):
            started = time.monotonic()
            with original(request, *arguments, **kwargs) as response:
                raw = response.read()
            payload = json.loads(request.data)
            calls.append({'prompt_sha256': hashlib.sha256(payload['prompt'].encode()).hexdigest(),
                          'options': payload['options'], 'reply': json.loads(raw),
                          'wall_seconds': round(time.monotonic() - started, 3)})
            return io.BytesIO(raw)
        urllib.request.urlopen = capture
        try:
            accepted = propose_from_transcript(segments, job['duration'], max_chunks=1, timeout=300,
                                                 model=model, on_event=lambda event, details: events.append({'event': event, **details}))
        finally:
            urllib.request.urlopen = original
        rows.append({'model': model, 'accepted': accepted, 'events': events, 'calls': calls})
        print(model, 'accepted', len(accepted), 'events', events[-1], flush=True)
    args.output.write_text(json.dumps({'job': args.job, 'language': job.get('language'),
                                       'runs': rows, 'production_selection_changed': False},
                                      ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
