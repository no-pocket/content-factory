"""Run one authorized local fixture through the isolated pipeline container."""
from pathlib import Path

from app.store import new_job, load
from app.worker import process


source = Path('/sample/videoplayback.mp4')
if not source.is_file():
    raise SystemExit(f'Missing test video: {source}')
job = new_job(source, source.name, 'test fixture', 'User-provided test video')
print(f'TEST_JOB={job["id"]}', flush=True)
process(job['id'])
result = load(job['id'])
print(f'STATUS={result["status"]} CANDIDATES={len(result["candidates"])}', flush=True)
if result.get('error'):
    print(f'ERROR={result["error"]}', flush=True)
if result['status'] != 'NEEDS_REVIEW':
    raise SystemExit(1)
