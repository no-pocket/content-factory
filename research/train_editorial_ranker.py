"""Check gates by default; --train still requires a fixed human-approved config."""
import argparse,json
from pathlib import Path
from app.artifacts import digest
from app.editorial_models import summarize_training_records,check_training_eligibility,train_ranker


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('dataset',type=Path)
    parser.add_argument('--config',type=Path);parser.add_argument('--train',action='store_true');parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args();manifest=json.loads((args.dataset/'manifest.json').read_text(encoding='utf-8'));records=json.loads((args.dataset/'records.json').read_text(encoding='utf-8'))
    if digest({k:v for k,v in manifest.items() if k!='dataset_id'})!=manifest['dataset_id'] or digest(records)!=manifest['records_sha256']:
        raise ValueError('Dataset integrity mismatch')
    config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
    report=check_training_eligibility({**manifest,'training_summary':summarize_training_records(records)},config)
    result={'status':'ELIGIBLE_FOR_AUTHORIZED_EXPERIMENT' if report['eligible'] else 'BLOCKED','eligibility':report,'trained':False,'model_downloaded':False}
    if args.train:
        if args.output_dir is None:raise ValueError('Explicit output directory required')
        result=train_ranker({'manifest':manifest,'records':records},config,args.output_dir)
    print(json.dumps(result,sort_keys=True))
    return 0 if report['eligible'] and (not args.train or result.get('trained')) else 2


if __name__=='__main__':raise SystemExit(main())
