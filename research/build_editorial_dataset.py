"""Read-only by default. Export approved-to-process local job metadata, never media."""
import argparse
import hashlib
import json
from pathlib import Path
from app.editorial_dataset import build_dataset,input_hashes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs-dir',type=Path,required=True)
    parser.add_argument('--cutoff',required=True,help='UTC ISO timestamp')
    parser.add_argument('--cohort',help='Comma-separated job IDs; no automatic negative selection')
    parser.add_argument('--administrative-manifest',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--export-root',type=Path)
    args=parser.parse_args()
    admin=[]
    if args.administrative_manifest:
        admin=[row['id'] for row in json.loads(args.administrative_manifest.read_text(encoding='utf-8'))['rejected_jobs']]
    selected=set(args.cohort.split(','))|set(admin) if args.cohort else None
    files=[];jobs=[]
    for path in sorted(args.jobs_dir.glob('*.json')):
        if path.name.endswith('.transcript.json'):continue
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,dict) or not value.get('id'):continue
        if selected is None or value['id'] in selected:files.append(path);jobs.append(value)
    if selected and selected-{j['id'] for j in jobs}:raise ValueError('Requested cohort has missing jobs')
    raw={j['id']:hashlib.sha256(path.read_bytes()).hexdigest() for j,path in zip(jobs,files)}
    def reader():
        now={j['id']:hashlib.sha256(path.read_bytes()).hexdigest() for j,path in zip(jobs,files)}
        return input_hashes([json.loads(p.read_text(encoding='utf-8')) for p in files]) if now==raw else {'raw_snapshot_changed':'true'}
    config={'cutoff':args.cutoff,'seed':17,'dry_run':args.output_dir is None,
            'export_root':str(args.export_root) if args.export_root else None,'administrative_job_ids':admin,
            'raw_input_sha256':raw,'snapshot_reader':reader}
    result=build_dataset(jobs,config,args.output_dir)
    print(json.dumps({'dry_run':args.output_dir is None,'manifest':result['manifest']},sort_keys=True))


if __name__=='__main__':main()
