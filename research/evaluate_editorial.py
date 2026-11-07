"""Descriptive offline evaluation; refuses changed manifest/records hashes."""
import argparse,json
from pathlib import Path
from app.artifacts import digest
from app.editorial_dataset import evaluate_pool


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path)
    p.add_argument('--retrieval-ablation',action='store_true',help='No model calls; report eligible examples by held-out source')
    args=p.parse_args()
    manifest=json.loads((args.dataset/'manifest.json').read_text(encoding='utf-8'))
    records=json.loads((args.dataset/'records.json').read_text(encoding='utf-8'))
    identity=manifest.pop('dataset_id')
    if digest(manifest)!=identity or digest(records)!=manifest['records_sha256']:raise ValueError('Dataset integrity mismatch')
    result={'dataset_id':identity,'evaluation':evaluate_pool(records,{'dataset_id':identity})}
    if args.retrieval_ablation:
        from app.editorial_retrieval import select_examples
        families=sorted({r['source_group_id'] for r in records if not r['administrative']})
        folds=[]
        for family in families:
            rows=[r for r in records if r['source_group_id']==family and not r['administrative']]
            text=' '.join(r['text'] for r in rows)
            query={'source_group_id':family,'source_fingerprint':rows[0].get('source_fingerprint'),'text':text}
            hashes={r.get('versions',{}).get('brief_sha256') for r in rows}
            known=next(iter(hashes)) if len(hashes)==1 else None
            policy={'status':'APPROVED' if known and known!='UNKNOWN' else 'NONE','brief_sha256':known}
            examples=select_examples(query,{'manifest':{**manifest,'dataset_id':identity},'records':records},policy,
                {'context_window':4096,'generation_reserve':700,'context_tokens_upper_bound':0,'max_example_tokens':600})
            folds.append({'held_out_source':family,'selected_candidate_ids':[e['candidate_id'] for e in examples],
                'baseline_context_sha256':digest({'text':text}),'assisted_context_sha256':digest({'text':text}),
                'status':'READY_FOR_HUMAN_PILOT' if examples else 'NOT_EVALUATED_NO_ELIGIBLE_EXAMPLES'})
        result['retrieval_ablation']={'model_calls':0,'folds':folds,'holdout_labels_used':False,
            'inference':'ELIGIBILITY_ONLY_NOT_AN_EDITORIAL_GAIN_MEASUREMENT'}
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
