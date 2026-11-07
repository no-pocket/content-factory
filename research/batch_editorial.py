"""Idempotent authorized corpus preparation. Does not assign editorial ratings.

Run inside the worker image, with corpus mounted read-only at /sample.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.job_settings import normalize_job_settings
from app.service import create_job, retry_enqueue
from app.store import all_jobs, load
from research.evaluate_sprint import fingerprint, signals

BASELINE = normalize_job_settings({'whisper_model': 'base', 'ranker_mode': 'heuristic',
                                    'director_mode': 'heuristic', 'render_engine': 'ffmpeg'})


def prepare(folder: Path, cohort: str, rights_note: str, output: Path) -> list[dict]:
    if not rights_note.strip():
        raise PermissionError('Explicit corpus authorization required')
    records = []
    jobs = all_jobs()
    if output.is_file():
        frozen = json.loads(output.read_text(encoding='utf-8'))
        if frozen['cohort'] != cohort or frozen['settings'] != BASELINE:
            raise ValueError('Frozen corpus configuration conflict')
        corpus = [{k: row[k] for k in ('source', 'sha256')} for row in frozen.get('corpus', frozen['videos'])]
    else:
        corpus = [{'source': source.name, 'sha256': fingerprint(source)} for source in sorted(folder.iterdir())
                  if source.is_file() and source.suffix.lower() in {'.mp4', '.mov', '.mkv', '.webm'}]
    def persist():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'cohort': cohort, 'settings': BASELINE, 'corpus': corpus, 'videos': records},
                                     ensure_ascii=False, indent=2), encoding='utf-8')
    # Freeze all intended sources before queueing the first job; a partial submission
    # can resume without absorbing later additions or losing the rest of this round.
    persist()
    for entry in corpus:
        source = (folder / entry['source']).resolve()
        if source.parent != folder.resolve() or not source.is_file():
            raise ValueError('Frozen source missing or outside corpus directory')
        digest = fingerprint(source)
        if digest != entry['sha256']:
            raise ValueError('Frozen source changed; use a new cohort')
        existing = [j for j in jobs if j.get('source_fingerprint') == digest and
                    j.get('evaluation') == {'cohort': cohort, 'variant': 'baseline-heuristic-v1'}]
        if existing:
            job = existing[0]
            if job.get('settings') != BASELINE:
                raise ValueError('Cohort settings conflict; use a new cohort identifier')
            if job['status'] == 'QUEUE_FAILED':
                job = retry_enqueue(job['id'])
        else:
            with source.open('rb') as upload:
                job = create_job({'creator': 'Corpus de teste autorizado pelo usuário',
                                  'license_note': rights_note, 'rights_confirmed': True,
                                  'settings': BASELINE,
                                  'evaluation': {'cohort': cohort, 'variant': 'baseline-heuristic-v1'}},
                                 upload=upload, filename=source.name)
            jobs.append(job)
        records.append({'source': source.name, 'sha256': digest, 'job_id': job['id']})
        persist()
        print(f"{len(records)} {job['id']} {job['status']}", flush=True)
    return records


def observe(records: list[dict], output: Path, *, analyze: bool) -> None:
    last = {}
    while True:
        jobs = [load(r['job_id']) for r in records]
        for job in jobs:
            if last.get(job['id']) != job['status']:
                print(job['id'], job['status'], job.get('language', 'undetected'), flush=True)
                last[job['id']] = job['status']
        active = {'QUEUED', 'DOWNLOADING', 'TRANSCRIBING', 'DIRECTING', 'RENDERING'}
        if not any(j['status'] in active for j in jobs):
            break
        time.sleep(10)
    reports = []
    for job in jobs:
        item = {'job_id': job['id'], 'source': job['original_name'], 'status': job['status'],
                'language': job.get('language'), 'duration': job.get('duration'),
                'processing_runs': job.get('processing_runs'), 'error': job.get('error'),
                'candidates': [{k: c.get(k) for k in ('start', 'end', 'state', 'attempts', 'qc')}
                               for c in job['candidates']]}
        if analyze and job['status'] in {'NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'PARTIAL_FAILED'}:
            destination = output.parent / ('signals-' + job['id'] + '.json')
            if destination.is_file():
                item['signals_report'] = destination.name
            else:
                report = signals(job)
                destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                item['signals_report'] = destination.name
            print('signals', job['id'], flush=True)
        reports.append(item)
        output.with_name('corpus-results.json').write_text(json.dumps({'videos': reports, 'editorial_decisions': None},
                                                         ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--videos', type=Path, required=True)
    parser.add_argument('--cohort', required=True)
    parser.add_argument('--rights-note', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--signals', action='store_true')
    args = parser.parse_args()
    records = prepare(args.videos, args.cohort, args.rights_note, args.output)
    if args.wait:
        observe(records, args.output, analyze=args.signals)


if __name__ == '__main__':
    main()
