"""Real SIGKILL/restart experiment against isolated synthetic media and Redis.

Requires existing worker/redis images; no builds, downloads or production job mutations.
Keeps evidence under research/pytest_temp_recovery_real and a small JSON report.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path


def run(*args):
    return subprocess.run(list(args), capture_output=True, text=True, check=True).stdout.strip()


def main():
    workspace = Path(__file__).resolve().parents[1]
    qa = workspace / 'research' / 'pytest_temp_recovery_real' / uuid.uuid4().hex
    qa.mkdir(parents=True)
    for folder in ('work', 'input', 'output'):
        (qa / folder).mkdir()
    suffix = uuid.uuid4().hex[:8]
    redis_name = 'cf-recovery-redis-' + suffix
    worker_name = 'cf-recovery-worker-' + suffix
    names = []
    jid = str(uuid.uuid4())
    job_path = qa / 'work' / (jid + '.json')
    from app.job_settings import normalize_job_settings
    from app.quality import normalize_qc
    settings = normalize_job_settings({'ranker_mode': 'heuristic', 'director_mode': 'heuristic',
                                        'render_engine': 'ffmpeg', 'clip_count': 2,
                                        'min_seconds': 8, 'target_seconds': 8, 'max_seconds': 15})
    segments = [{'start': 0, 'end': 16, 'text': 'Synthetic recovery test, no editorial evaluation', 'words': []}]
    job = {'id': jid, 'status': 'QUEUED', 'source_type': 'upload', 'source': '/data/input/synthetic.mp4',
           'creator': 'SYNTHETIC FIXTURE', 'license_note': 'Generated test pattern and sine wave',
           'settings': settings, 'qc_settings': normalize_qc(), 'audio_expected': True,
           'candidates': [{'start': a, 'end': a+8, 'text': 'Synthetic recovery test', 'score': 0,
                           'reason': 'Synthetic fixture'} for a in (0, 8)],
           'approved': [], 'decision_history': []}
    job_path.write_text(json.dumps(job), encoding='utf-8')
    (qa / 'work' / (jid + '.transcript.json')).write_text(json.dumps({'language': 'en', 'segments': segments}), encoding='utf-8')
    report = {'synthetic': True, 'production_mutated': False, 'job': jid, 'qa_directory': str(qa)}
    try:
        run('docker', 'run', '--rm', '--network', 'none', '-v', str(qa) + ':/data',
            '--entrypoint', 'ffmpeg', 'content-factory-worker:latest', '-v', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-f', 'lavfi', '-i', 'sine=frequency=440',
            '-t', '16', '-c:v', 'libx264', '-c:a', 'aac', '/data/input/synthetic.mp4')
        run('docker', 'run', '-d', '--name', redis_name, '--network', 'content-factory_default',
            '--tmpfs', '/data', 'redis:7-alpine')
        names.append(redis_name)
        for _ in range(50):
            try:
                if run('docker', 'exec', redis_name, 'redis-cli', 'PING') == 'PONG':
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(.1)
        run('docker', 'exec', redis_name, 'redis-cli', 'LPUSH', 'clips:queue', jid)
        run('docker', 'run', '-d', '--name', worker_name, '--network', 'content-factory_default',
            '-v', str(qa) + ':/data', '-v', str(workspace / 'app') + ':/app/app:ro',
            '-e', 'DATA_DIR=/data', '-e', f'REDIS_URL=redis://{redis_name}:6379/0',
            '--entrypoint', 'python', 'content-factory-worker:latest', '-m', 'app.worker')
        names.append(worker_name)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            current = json.loads(job_path.read_text(encoding='utf-8'))
            first, second = current['candidates']
            if first.get('state') in {'VALID', 'WARNING'} and second.get('state') == 'RENDERING':
                preserved = qa / 'output' / jid / 'candidate_1.mp4'
                before = hashlib.sha256(preserved.read_bytes()).hexdigest()
                run('docker', 'kill', '--signal', 'KILL', worker_name)
                break
            if current['status'] in {'FAILED', 'PARTIAL_FAILED', 'NEEDS_REVIEW'}:
                raise RuntimeError('Missed render interruption checkpoint: ' + current['status'])
            time.sleep(.02)
        else:
            raise TimeoutError('Render checkpoint not reached')
        killed = json.loads(job_path.read_text(encoding='utf-8'))
        report['after_kill'] = {'status': killed['status'], 'states': [c.get('state') for c in killed['candidates']],
                                'attempts': [c.get('attempts') for c in killed['candidates']],
                                'processing': run('docker', 'exec', redis_name, 'redis-cli', 'LLEN', 'clips:processing')}
        run('docker', 'start', worker_name)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            current = json.loads(job_path.read_text(encoding='utf-8'))
            if current['status'] in {'NEEDS_REVIEW', 'FAILED', 'PARTIAL_FAILED'}:
                break
            time.sleep(.1)
        else:
            raise TimeoutError('Restart did not finish')
        after = hashlib.sha256(preserved.read_bytes()).hexdigest()
        for _ in range(30):
            processing = run('docker', 'exec', redis_name, 'redis-cli', 'LLEN', 'clips:processing')
            if processing == '0':
                break
            time.sleep(.1)
        report['after_restart'] = {'status': current['status'], 'states': [c.get('state') for c in current['candidates']],
                                   'attempts': [c.get('attempts') for c in current['candidates']],
                                   'first_master_unchanged': before == after,
                                   'first_master_sha256_before': before, 'first_master_sha256_after': after,
                                   'processing': processing,
                                   'processing_runs': current.get('processing_runs')}
        assert current['status'] == 'NEEDS_REVIEW', current.get('error')
        assert before == after
        assert [c['attempts'] for c in current['candidates']] == [1, 2]
        assert processing == '0'
        # Corrupt only the synthetic second master, then prove QC rejects it and the
        # exhausted attempt limit blocks replacement without touching the first result.
        (qa / 'output' / jid / 'candidate_2.mp4').write_bytes(b'INTENTIONAL SYNTHETIC CORRUPTION')
        code = ("import json; from app.service import verify_existing,retry_candidate,Conflict; "
                f"job=verify_existing('{jid}'); "
                "print(json.dumps({'status':job['status'],'states':[c['state'] for c in job['candidates']]})); "
                "\ntry:\n retry_candidate('" + jid + "',1)\nexcept Conflict as exc:\n print('LIMIT_BLOCKED',str(exc))")
        rejection = run('docker', 'exec', worker_name, 'python', '-c', code)
        assert 'PARTIAL_FAILED' in rejection and 'LIMIT_BLOCKED Attempt limit exhausted' in rejection
        assert hashlib.sha256(preserved.read_bytes()).hexdigest() == before
        report['corruption_and_limit'] = rejection
        report['passed'] = True
    except Exception as exc:
        report.update(passed=False, error=str(exc))
        raise
    finally:
        for name in reversed(names):
            assert name.startswith(('cf-recovery-worker-', 'cf-recovery-redis-'))
            if 'worker' in name:
                (qa / 'worker.log').write_text(run('docker', 'logs', name), encoding='utf-8')
            run('docker', 'rm', '-f', name)  # only the two uniquely named containers created here; no volumes
        target = workspace / 'research' / 'sprint' / 'recovery-real.json'
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(target, flush=True)


if __name__ == '__main__':
    main()
