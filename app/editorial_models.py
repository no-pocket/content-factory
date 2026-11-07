"""Offline logistic research gates. No startup imports, online training or promotion."""
from __future__ import annotations
from collections import Counter
from importlib.metadata import version
import json
import math
from pathlib import Path
import statistics
import uuid
from .artifacts import digest
from .editorial_features import FEATURES

GATES={'independent_groups':50,'eligible_candidates':150,'positives':30,'negatives':30,
       'positive_groups':10,'negative_groups':10,'holdout_groups':15,'train_positive_groups':5,'train_negative_groups':5}


def _eligible(row):
    grade=row.get('content_grade');versions=row.get('versions',{})
    return (row.get('human_confirmed') is True and row.get('authorized') is True and not row.get('administrative')
            and type(grade) is int and 0<=grade<=3 and row.get('split') in ('train','test')
            and row.get('features',{}).get('schema_version')=='editorial-features-v1'
            and all(isinstance(versions.get(key),str) and len(versions[key])==64 and
                    all(c in '0123456789abcdef' for c in versions[key]) for key in ('brief_sha256','component_snapshot_id')))


def summarize_training_records(records):
    rows=[r for r in records if _eligible(r)]
    counts={'independent_groups':len({r['source_group_id'] for r in rows}),'eligible_candidates':len(rows),
            'holdout_groups':len({r['source_group_id'] for r in rows if r['split']=='test'})}
    for name,positive in (('positive',True),('negative',False)):
        selected=[r for r in rows if (r['content_grade']>=2)==positive]
        counts['positives' if positive else 'negatives']=len(selected)
        counts[name+'_groups']=len({r['source_group_id'] for r in selected})
        counts['train_'+name+'_groups']=len({r['source_group_id'] for r in selected if r['split']=='train'})
    partitions={}
    for row in rows:partitions.setdefault(row['source_group_id'],set()).add(row['split'])
    counts['cross_split_groups']=sum(len(s)>1 for s in partitions.values())
    counts['languages']=sorted({r.get('language','UNKNOWN') for r in rows})
    return counts


def check_training_eligibility(manifest: dict,config: dict) -> dict:
    counts=manifest.get('training_summary',{});reasons=[]
    for key,minimum in GATES.items():
        if counts.get(key,0)<minimum:reasons.append('INSUFFICIENT_'+key.upper())
    if counts.get('cross_split_groups',0):reasons.append('SOURCE_FAMILY_CROSSES_SPLIT')
    if not {'pt','en'}<=set(counts.get('languages',[])):reasons.append('PT_EN_COVERAGE_INSUFFICIENT')
    data_eligible=not reasons
    approval=config.get('approval') or {}
    approved=(approval.get('kind')=='human' and approval.get('status')=='APPROVED' and
              isinstance(approval.get('actor'),str) and bool(approval['actor'].strip()) and
              approval.get('dataset_id')==manifest.get('dataset_id') and
              approval.get('config_sha256')==digest({k:v for k,v in config.items() if k!='approval'}))
    if not approved:reasons.append('EXPERIMENT_NOT_APPROVED')
    return {'eligible':not reasons,'data_eligible':data_eligible,'reasons':reasons,'counts':counts,
            'thresholds':GATES.copy(),'gate_version':'proposed-editorial-gates-v1','target':'content_grade_ge_2',
            'promotion':'NOT_AUTHORIZED_BY_TRAINING_GATE'}


def _feature_names(names):
    if not isinstance(names,list) or not 1<=len(names)<=12 or len(set(names))!=len(names) or set(names)-set(FEATURES):
        raise ValueError('Invalid fixed feature list')
    return names


def _value(row,name):
    values=row.get('features',{}).get('values',row)
    value=values.get(name)
    if value is not None and (type(value) not in (float,int) or not math.isfinite(value) or value<0):
        raise ValueError('Invalid inference feature')
    return value


def fit_preprocessing(train,names):
    names=_feature_names(names)
    if not train:raise ValueError('No training rows')
    medians=[];means=[];scales=[]
    for name in names:
        known=[_value(row,name) for row in train if _value(row,name) is not None]
        median=statistics.median(known) if known else 0.
        values=[median if _value(row,name) is None else _value(row,name) for row in train]
        mean=statistics.mean(values);scale=statistics.pstdev(values) or 1.
        medians.append(median);means.append(mean);scales.append(scale)
    return {'feature_names':names,'medians':medians,'means':means,'scales':scales,'missing_indicators':'all_features'}


def transform(rows,preprocessing):
    names=preprocessing['feature_names'];result=[]
    for row in rows:
        raw=[_value(row,name) for name in names]
        imputed=[preprocessing['medians'][i] if value is None else value for i,value in enumerate(raw)]
        result.append([(value-preprocessing['means'][i])/preprocessing['scales'][i] for i,value in enumerate(imputed)]+[int(v is None) for v in raw])
    return result


def prepare_training_split(records,names):
    rows=[r for r in records if _eligible(r)]
    if summarize_training_records(rows)['cross_split_groups']:raise ValueError('Family crosses train/test')
    train=[r for r in rows if r['split']=='train']
    preprocessing=fit_preprocessing(train,names)
    return {'preprocessing':preprocessing,'x_train':transform(train,preprocessing),
            'y_train':[int(r['content_grade']>=2) for r in train],
            'train_groups':[r['source_group_id'] for r in train],
            'holdout_ids':[r['candidate_id'] for r in rows if r['split']=='test']}


def score_candidates(features: list[dict],artifact: dict | None) -> list[dict]:
    def baseline(reason):return [{'input_index':i,'score':None,'ranker_used':'baseline','fallback_reason':reason} for i in range(len(features))]
    if artifact is None:return baseline('MODEL_UNAVAILABLE')
    try:
        if artifact['schema_version']!='editorial-logistic-v1' or artifact['artifact_id']!=digest({k:v for k,v in artifact.items() if k!='artifact_id'}):
            raise ValueError('Model integrity mismatch')
        prep=artifact['preprocessing'];names=_feature_names(prep['feature_names']);size=len(names)
        if any(len(prep[key])!=size for key in ('medians','means','scales')) or len(artifact['weights'])!=2*size:
            raise ValueError('Model shape mismatch')
        numeric=artifact['weights']+[artifact['intercept']]+prep['medians']+prep['means']+prep['scales']
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in numeric) or min(prep['scales'])<=0:
            raise ValueError('Invalid model numbers')
        values=transform(features,prep);result=[]
        for i,row in enumerate(values):
            z=artifact['intercept']+sum(a*b for a,b in zip(row,artifact['weights']))
            probability=1/(1+math.exp(-max(-700,min(700,z))))
            result.append({'input_index':i,'score':probability,'ranker_used':'offline_logistic_research','fallback_reason':None})
        return result
    except (ValueError,TypeError,KeyError,OverflowError):return baseline('INVALID_ARTIFACT')


def train_ranker(dataset: dict,config: dict,output_dir: Path) -> dict:
    """Refuses before imports/writes if data or fixed human experiment approval fail."""
    manifest=dataset['manifest'];rows=dataset['records']
    report=check_training_eligibility({**manifest,'training_summary':summarize_training_records(rows)},config)
    if not report['eligible']:return {'status':'BLOCKED','eligibility':report,'trained':False}
    if config.get('dataset_id')!=manifest.get('dataset_id'):raise ValueError('Fixed experiment dataset mismatch')
    names=_feature_names(config.get('features',[]));seed=config.get('seed',17);regularization=config.get('regularization_c',1.)
    if type(seed) is not int or type(regularization) not in (float,int) or not math.isfinite(regularization) or regularization<=0:
        raise ValueError('Invalid fixed training configuration')
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GroupKFold
        import numpy as np
        if version('scikit-learn')!='1.9.1':raise ImportError('Unverified optional dependency version')
    except ImportError:return {'status':'DEPENDENCY_UNAVAILABLE','trained':False,'reason':'Optional isolated ML dependencies unavailable or unverified'}
    target=Path(output_dir).resolve();root=Path(config['export_root']).resolve()
    if target==root or not target.is_relative_to(root) or target.exists():raise ValueError('Unsafe or existing model destination')
    train=[r for r in rows if _eligible(r) and r['split']=='train']
    labels=np.array([int(r['content_grade']>=2) for r in train]);groups=np.array([r['source_group_id'] for r in train])
    scores=[]
    def fitted(part):
        prep=fit_preprocessing(part,names);x=transform(part,prep);y=[int(r['content_grade']>=2) for r in part]
        counts=Counter(r['source_group_id'] for r in part)
        estimator=LogisticRegression(C=regularization,max_iter=1000,solver='lbfgs',random_state=seed)
        estimator.fit(x,y,sample_weight=[1/counts[r['source_group_id']] for r in part])
        return estimator,prep
    for fit_indices,validation_indices in GroupKFold(n_splits=5).split(np.zeros(len(train)),labels,groups):
        if len(set(labels[fit_indices]))<2 or len(set(labels[validation_indices]))<2:
            return {'status':'BLOCKED','trained':False,'reason':'CV_CLASS_COVERAGE_INSUFFICIENT'}
        estimator,prep=fitted([train[i] for i in fit_indices])
        predicted=estimator.predict(transform([train[i] for i in validation_indices],prep))
        scores.append(float((predicted==labels[validation_indices]).mean()))
    estimator,prep=fitted(train)
    artifact={'schema_version':'editorial-logistic-v1','status':'EVALUATION_ONLY','dataset_id':manifest['dataset_id'],
        'config_sha256':digest({k:v for k,v in config.items() if k!='approval'}),'approval':config['approval'],
        'preprocessing':prep,'weights':estimator.coef_[0].tolist(),'intercept':float(estimator.intercept_[0]),
        'seed':seed,'regularization_c':regularization,'target':'content_grade_ge_2',
        'dependencies':{p:version(p) for p in ('scikit-learn','numpy','scipy')},
        'cv_accuracy_by_family_fold':scores,'holdout_evaluated':False,'promotion':'NOT_PROMOTED'}
    artifact['artifact_id']=digest(artifact)
    root.mkdir(parents=True,exist_ok=True)
    if not target.parent.is_dir():raise ValueError('Model parent must already exist')
    # Destination is always new, and no active-model pointer is changed.
    target.mkdir(exist_ok=False)
    temporary=target/('model.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(artifact,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        temporary.replace(target/'model.json')
    finally:temporary.unlink(missing_ok=True)
    return {'status':'TRAINED_FOR_EVALUATION_ONLY','trained':True,'artifact_id':artifact['artifact_id'],'eligibility':report,'holdout_evaluated':False}
