"""Descriptive offline evaluation; refuses changed manifest/records hashes."""
import argparse,json
from pathlib import Path
from app.artifacts import digest
from app.editorial_dataset import evaluate_pool


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path);args=p.parse_args()
    manifest=json.loads((args.dataset/'manifest.json').read_text(encoding='utf-8'))
    records=json.loads((args.dataset/'records.json').read_text(encoding='utf-8'))
    identity=manifest.pop('dataset_id')
    if digest(manifest)!=identity or digest(records)!=manifest['records_sha256']:raise ValueError('Dataset integrity mismatch')
    print(json.dumps({'dataset_id':identity,'evaluation':evaluate_pool(records,{'dataset_id':identity})},sort_keys=True))


if __name__=='__main__':main()
