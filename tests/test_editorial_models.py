import copy
import pytest


def synthetic_records():
    rows=[]
    for group in range(60):
        for i in range(3):
            rows.append({'candidate_id':f'{group}-{i}','source_group_id':f'g{group}','split':'test' if group<15 else 'train',
                'human_confirmed':True,'authorized':True,'administrative':False,'content_grade':3 if i%2 else 0,
                'language':'pt' if group%2 else 'en','versions':{'brief_sha256':'b'*64,'component_snapshot_id':'c'*64},
                'features':{'schema_version':'editorial-features-v1','values':{'duration_seconds':10+group,'word_count':30+i}}})
    return rows


def test_training_refuses_insufficient_independent_groups(tmp_path):
    from app.editorial_models import check_training_eligibility,train_ranker
    data={'manifest':{'dataset_id':'d'*64,'source_groups':5,'eligible_content_candidates':0},'records':[]}
    report=check_training_eligibility(data['manifest'],{})
    assert not report['eligible'] and 'INSUFFICIENT_INDEPENDENT_GROUPS' in report['reasons']
    result=train_ranker(data,{},tmp_path/'must-not-exist')
    assert result['status']=='BLOCKED' and not (tmp_path/'must-not-exist').exists()


def test_pairwise_better_but_bad_is_not_positive():
    from app.editorial_models import summarize_training_records
    rows=synthetic_records()[:3]
    for row in rows:
        row['content_grade']=None;row['relative_assessment']={'all_options_below_bar':True,'preferred_candidate_id':rows[0]['candidate_id']}
    summary=summarize_training_records(rows)
    assert summary['eligible_candidates']==0 and summary['positives']==0


def test_test_labels_never_fit_preprocessing():
    from app.editorial_models import prepare_training_split
    rows=synthetic_records()
    first=prepare_training_split(rows,['duration_seconds','word_count'])
    changed=copy.deepcopy(rows)
    for row in changed:
        if row['split']=='test':row['features']['values']['duration_seconds']=1e9;row['content_grade']=3
    second=prepare_training_split(changed,['duration_seconds','word_count'])
    assert first['preprocessing']==second['preprocessing'] and first['x_train']==second['x_train']
    assert first['y_train']==second['y_train'] and len(first['train_groups'])==135


def test_gate_requires_fixed_human_approval_and_has_class_source_counts():
    from app.editorial_models import summarize_training_records,check_training_eligibility
    manifest={'training_summary':summarize_training_records(synthetic_records())}
    report=check_training_eligibility(manifest,{})
    assert report['data_eligible'] and not report['eligible']
    assert report['counts']['holdout_groups']==15
    assert 'EXPERIMENT_NOT_APPROVED' in report['reasons']


def test_missing_or_changed_artifact_has_explicit_baseline_fallback():
    from app.editorial_models import score_candidates
    rows=[{'duration_seconds':10,'word_count':20}]
    assert score_candidates(rows,None)[0]['fallback_reason']=='MODEL_UNAVAILABLE'
    assert score_candidates(rows,{'schema_version':'unsafe','weights':[1]})[0]['fallback_reason']=='INVALID_ARTIFACT'


def test_json_inference_keeps_missing_indicator_and_parameter_order():
    from app.artifacts import digest
    from app.editorial_models import score_candidates
    artifact={'schema_version':'editorial-logistic-v1','preprocessing':{'feature_names':['duration_seconds'],
        'medians':[10.],'means':[10.],'scales':[2.]},'weights':[1.,-1.],'intercept':0.}
    artifact['artifact_id']=digest(artifact)
    result=score_candidates([{'duration_seconds':12.},{'duration_seconds':None}],artifact)
    assert result[0]['score']==pytest.approx(.7310585786)
    assert result[1]['score']==pytest.approx(.2689414214)
    artifact['weights'][0]=float('nan')
    assert score_candidates([{}],artifact)[0]['fallback_reason']=='INVALID_ARTIFACT'
