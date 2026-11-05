"""Measure one real proposal request assembled by the production ranker."""
import json
import sys
import time
import urllib.request

from app.ranker import propose_from_transcript


transcript = json.loads(open(sys.argv[1], encoding='utf-8').read())
segments = transcript['segments']
captured = []
original = urllib.request.urlopen


class FakeReply:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return b'{"response":"{\\"clips\\":[]}"}'


def capture(request, timeout):
    captured.append(request)
    return FakeReply()


urllib.request.urlopen = capture
try:
    propose_from_transcript(segments, segments[-1]['end'], max_chunks=1)
finally:
    urllib.request.urlopen = original

request = captured[0]
body = json.loads(request.data)
print(f'PROMPT_CHARS={len(body["prompt"])} SEGMENTS=50', flush=True)
start = time.monotonic()
with original(request, timeout=240) as response:
    result = json.load(response)
print(f'WALL_SECONDS={time.monotonic()-start:.1f}', flush=True)
for key in ('total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration',
            'eval_count', 'eval_duration', 'done_reason'):
    print(f'{key}={result.get(key)}', flush=True)
