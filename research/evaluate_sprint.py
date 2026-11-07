"""Reproducible local evidence collection; never writes invented editorial decisions.

python -m research.evaluate_sprint inventory --videos /sample --output research/sprint/inventory.json
python -m research.evaluate_sprint signals --job ID --output research/sprint/signals.json
python -m research.evaluate_sprint models --job ID --output research/sprint/models.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from app.core import get_duration, propose_clips
from app.editorial import summarize
from app.job_settings import normalize_job_settings
from app.signals import extract_signals, boundary_experiment
from app.store import JOBS, all_jobs, load


def fingerprint(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def inventory(folder: Path, target: int = 20):
    records = []
    for path in sorted(folder.rglob('*')):
        if path.is_file() and path.suffix.lower() in {'.mp4', '.mov', '.mkv', '.webm'}:
            record = {'file': path.name, 'bytes': path.stat().st_size, 'sha256': fingerprint(path),
                      'authorization': 'confirm per submission; presence on disk is not permission'}
            try:
                record['duration'] = get_duration(path)
            except Exception as exc:
                record['error'] = str(exc)
            records.append(record)
    unique = len({r['sha256'] for r in records})
    return {'videos': records, 'unique_videos': unique, 'round_target': target, 'additional_for_round': max(0, target - unique),
            'additional_for_20': max(0, 20 - unique),
            'additional_for_30': max(0, 30 - unique), 'editorial': summarize(all_jobs())}


def signals(job):
    transcript = json.loads((JOBS / (job['id'] + '.transcript.json')).read_text())
    settings = normalize_job_settings(job.get('settings'))
    baseline = propose_clips(transcript['segments'], job['duration'], count=settings['clip_count'],
                             target=settings['target_seconds'], min_seconds=settings['min_seconds'],
                             max_seconds=settings['max_seconds'])
    evidence = extract_signals(Path(job['source']))
    return {'job': job['id'], 'source_sha256': fingerprint(Path(job['source'])), 'settings': settings,
            'signals': evidence, 'baseline': baseline,
            'experiment': boundary_experiment(baseline, evidence, job['duration'],
                                               min_seconds=settings['min_seconds'], max_seconds=settings['max_seconds']),
            'editorial_verdict': None, 'production_selection_changed': False}


def models(job):
    transcript = json.loads((JOBS / (job['id'] + '.transcript.json')).read_text())
    segments = [{k: s[k] for k in ('start', 'end', 'text')} for s in transcript['segments'][:12]]
    prompt = ('Avalie estes segmentos de um vídeo autorizado e escolha um corte com contexto completo. '
              'Retorne JSON com start_segment, end_segment (índices de 0 a 11), hook e reason. '
              'Não invente texto, prefira fechamento completo.\n' + json.dumps(segments, ensure_ascii=False))
    url = os.getenv('OLLAMA_URL', 'http://ollama:11434').rstrip('/')
    with urllib.request.urlopen(url + '/api/tags', timeout=10) as response:
        available = json.load(response)['models']
    results = []
    for name in ('qwen2.5:1.5b', 'qwen2.5:3b'):
        if not any(m['name'] == name for m in available):
            results.append({'model': name, 'error': 'not installed; not downloaded'})
            continue
        for repeat in range(3):  # cold/warm runs kept distinct
            started = time.monotonic()
            payload = {'model': name, 'prompt': prompt, 'format': 'json', 'stream': False,
                       'keep_alive': '2m', 'options': {'temperature': 0, 'seed': 42, 'num_predict': 256, 'num_ctx': 4096}}
            result = {'model': name, 'repeat': repeat, 'options': payload['options']}
            try:
                req = urllib.request.Request(url + '/api/generate', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=300) as response:
                    reply = json.load(response)
                result.update({k: reply.get(k) for k in ('response', 'done_reason', 'total_duration', 'load_duration',
                                                        'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration')})
                try:
                    parsed = json.loads(reply['response'])
                    result['contract_valid'] = (type(parsed.get('start_segment')) is int and
                        type(parsed.get('end_segment')) is int and
                        0 <= parsed['start_segment'] <= parsed['end_segment'] < len(segments) and
                        all(isinstance(parsed.get(k), str) and parsed[k].strip() for k in ('hook', 'reason')) and
                        reply.get('done_reason') == 'stop')
                except (ValueError, TypeError):
                    result['contract_valid'] = False
            except Exception as exc:
                result['error'] = str(exc)
            result['wall_seconds'] = round(time.monotonic() - started, 3)
            results.append(result)
    return {'job': job['id'], 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'segment_count': len(segments), 'available': available, 'runs': results,
            'editorial_verdict': None, 'default_changed': False,
            'limits': 'One video, one task prompt. No quality verdict or general reliability estimate.'}


def pipeline_models(job):
    """Use the actual production prompt/validators rather than a benchmark-only contract."""
    from app.ranker import propose_from_transcript, rerank_with_ollama
    from app.director import direct_edit
    from app.timeline import build_timeline
    transcript = json.loads((JOBS / (job['id'] + '.transcript.json')).read_text())
    segments = transcript['segments'][:12]
    baseline = propose_clips(segments, job['duration'], count=1)
    if not baseline:
        raise ValueError('No comparable baseline')
    rerank_candidates = propose_clips(transcript['segments'], job['duration'], count=6)
    original = urllib.request.urlopen
    calls = []
    current_task = 'proposal'
    import io
    def measured(request, *args, **kwargs):
        started = time.monotonic()
        with original(request, *args, **kwargs) as response:
            raw = response.read()
        reply = json.loads(raw)
        payload = json.loads(request.data)
        calls.append({'task': current_task, 'wall_seconds': round(time.monotonic() - started, 3),
                      'prompt_sha256': hashlib.sha256(payload['prompt'].encode()).hexdigest(),
                      'options': payload['options'],
                      **{k: reply.get(k) for k in ('done_reason', 'prompt_eval_count', 'eval_count',
                                                  'prompt_eval_duration', 'eval_duration', 'load_duration')}})
        return io.BytesIO(raw)
    results = []
    url = os.getenv('OLLAMA_URL', 'http://ollama:11434').rstrip('/')
    with original(url + '/api/tags', timeout=10) as response:
        available = json.load(response)['models']
    for name in ('qwen2.5:1.5b', 'qwen2.5:3b'):
        if not any(m['name'] == name for m in available):
            continue
        for repeat in range(2):
            events = []
            calls = []
            urllib.request.urlopen = measured
            try:
                current_task = 'proposal'
                proposals = propose_from_transcript(segments, job['duration'], max_chunks=1, timeout=300,
                                                     model=name,
                                                     on_event=lambda event, detail: events.append({'task': current_task, 'event': event, **detail}))
                current_task = 'rerank'
                reranked = rerank_with_ollama(rerank_candidates, count=3, timeout=300, model=name,
                                              on_event=lambda event, detail: events.append({'task': current_task, 'event': event, **detail}))
                current_task = 'director'
                hints, engine = direct_edit(baseline[0], {}, mode='ollama', model=name)
                timeline = build_timeline(baseline[0], segments, edit=hints, assets={})
            finally:
                urllib.request.urlopen = original
            with original(url + '/api/ps', timeout=10) as response:
                resources = json.load(response)
            results.append({'model': name, 'repeat': repeat, 'proposals': proposals,
                            'accepted_proposals': len(proposals), 'director_engine': engine,
                            'reranked': reranked, 'director_hints': hints,
                            'validated_text_layers': timeline['layers']['text'],
                            'calls': calls, 'events': events,
                            'resource_snapshot': resources})
    return {'job': job['id'], 'language': job.get('language'), 'benchmark_version': 2,
            'segment_count': len(segments), 'baseline': baseline, 'rerank_candidates': rerank_candidates,
            'available': available, 'runs': results, 'editorial_verdict': None,
            'default_changed': False, 'limits': 'One video, two repeats, production prompts/validators. No human editorial ratings.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['inventory', 'signals', 'models', 'pipeline_models'])
    parser.add_argument('--videos', type=Path)
    parser.add_argument('--job')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--target', type=int, default=20)
    args = parser.parse_args()
    report = inventory(args.videos, args.target) if args.mode == 'inventory' else globals()[args.mode](load(args.job))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
