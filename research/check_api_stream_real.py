"""Upload an authorized large corpus file to isolated API/Redis, without rendering."""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import subprocess
import time
import uuid
from pathlib import Path


def run(*args):
    return subprocess.run(list(args), capture_output=True, text=True, check=True).stdout.strip()


def main():
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / 'research/sprint/inventory.json').read_text(encoding='utf-8'))
    source_record = max(inventory['videos'], key=lambda v: v['bytes'])
    source = root.parent / '_videos_test' / source_record['file']
    qa = root / 'research/pytest_temp_api_stream' / uuid.uuid4().hex
    qa.mkdir(parents=True)
    suffix = uuid.uuid4().hex[:8]
    redis_name, api_name = 'cf-stream-redis-' + suffix, 'cf-stream-api-' + suffix
    token = uuid.uuid4().hex
    env_file = qa / 'api.env'
    env_file.write_text('CONTENT_FACTORY_API_TOKEN=' + token + '\n', encoding='utf-8')
    names = []
    report = {'authorized_corpus_media': True, 'production_mutated': False,
              'source': source.name, 'bytes': source.stat().st_size, 'editorial_decisions_created': 0}
    try:
        run('docker', 'run', '-d', '--name', redis_name, '--network', 'content-factory_default',
            '--tmpfs', '/data', 'redis:7-alpine')
        names.append(redis_name)
        run('docker', 'run', '-d', '--name', api_name, '--network', 'content-factory_default',
            '-p', '127.0.0.1:8514:8510', '-v', str(qa) + ':/data', '-v', str(root / 'app') + ':/app/app:ro',
            '--env-file', str(env_file), '-e', 'DATA_DIR=/data', '-e', 'CONTENT_FACTORY_API_BIND=0.0.0.0',
            '-e', 'REDIS_URL=redis://' + redis_name + ':6379/0', '--entrypoint', 'python',
            'content-factory-worker:latest', '-m', 'app.api')
        names.append(api_name)
        env_file.unlink()
        for attempt in range(100):
            try:
                connection = http.client.HTTPConnection('127.0.0.1', 8514, timeout=2)
                connection.request('GET', '/v1/jobs', headers={'Authorization': 'Bearer ' + token})
                response = connection.getresponse(); response.read(); connection.close()
                if response.status == 200:
                    break
            except OSError:
                pass
            time.sleep(.1)
        else:
            raise TimeoutError('Isolated API did not start')
        with source.open('rb') as handle:
            expected_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
        assert expected_hash == source_record['sha256']
        metadata = {'filename': source.name, 'creator': 'Authorized corpus transport QA',
                    'license_note': 'User authorized these 12 videos for this sprint; isolated transport test only.',
                    'rights_confirmed': True, 'settings': {'ranker_mode': 'heuristic'}}
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/octet-stream',
                   'Content-Length': str(source.stat().st_size),
                   'X-Content-Factory-Metadata': base64.b64encode(json.dumps(metadata, ensure_ascii=False).encode()).decode()}
        connection = http.client.HTTPConnection('127.0.0.1', 8514, timeout=120)
        started = time.monotonic()
        with source.open('rb') as handle:
            connection.request('POST', '/v1/jobs/upload', body=handle, headers=headers)
        response = connection.getresponse()
        reply = json.loads(response.read()); connection.close()
        report.update(http_status=response.status, wall_seconds=round(time.monotonic() - started, 3))
        assert response.status == 201, reply
        assert reply['source_fingerprint'] == expected_hash
        assert reply['original_name'] == source.name
        queued = run('docker', 'exec', redis_name, 'redis-cli', 'LLEN', 'clips:queue')
        assert queued == '1'
        report.update(job_id=reply['id'], status=reply['status'], sha256=expected_hash,
                      binary_integrity_verified=True, queued=1,
                      memory_after_upload=run('docker', 'stats', '--no-stream', '--format', '{{.MemUsage}}', api_name),
                      passed=True)
    except Exception as exc:
        report.update(passed=False, error=str(exc))
        raise
    finally:
        env_file.unlink(missing_ok=True)
        for name in reversed(names):
            assert name.startswith(('cf-stream-api-', 'cf-stream-redis-'))
            run('docker', 'rm', '-f', name)  # only isolated containers created in this experiment
        destination = root / 'research/sprint/api-stream-real.json'
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(destination, flush=True)


if __name__ == '__main__':
    main()
