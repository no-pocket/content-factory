import pytest

def rows(grades,decisions=None,scores=None):
    return [{'source_group_id':'family','comparison_set_id':'pool','candidate_id':str(i),'artifact_id':str(i),
             'content_grade':g,'decision':(decisions or ['APPROVED']*len(grades))[i],
             'rank':i,'score':(scores or list(range(len(grades),0,-1)))[i], 'human_confirmed':True}
            for i,g in enumerate(grades)]


def test_small_pool_uses_three_slots_and_unknown_is_not_zero():
    from app.editorial_dataset import evaluate_pool
    r=evaluate_pool(rows([3,2]),{})
    assert r['precision_at_3']==pytest.approx(2/3) and r['acceptance_at_3_clean']==pytest.approx(2/3)
    unknown=evaluate_pool(rows([3,None]),{})
    assert unknown['precision_at_3'] is None and unknown['grade_query_coverage']==0
    assert unknown['queries_generated']==1


def test_linear_ndcg_ties_and_zero_idcg_are_explicit():
    from app.editorial_dataset import evaluate_pool
    r=evaluate_pool(rows([3,0,1],scores=[1,1,1]),{})
    import math
    ideal=3+1/math.log2(3)
    expected=(4/3)*sum(1/math.log2(i+2) for i in range(3))/ideal
    assert r['ndcg_at_3']==pytest.approx(expected)
    assert evaluate_pool(rows([0,0]),{})['ndcg_at_3'] is None
    assert evaluate_pool(rows([0,0]),{})['excluded_zero_idcg']==1


def test_conditional_and_unknown_decisions_remain_separate():
    from app.editorial_dataset import evaluate_pool
    r=evaluate_pool(rows([2,1,0],['APPROVED','APPROVED_WITH_ADJUSTMENTS','REJECTED']),{})
    assert r['acceptance_at_3_clean']==pytest.approx(1/3)
    assert r['acceptance_at_3_adjusted']==pytest.approx(1/3)
    records=rows([3]);records[0]['human_confirmed']=False
    assert evaluate_pool(records,{})['acceptance_at_3_clean'] is None


def test_dimension_coverage_and_relative_better_does_not_imply_positive():
    from app.editorial_dataset import evaluate_pool
    r=rows([0,0],['REJECTED','REJECTED'])
    for row in r:row['candidate_version']=1
    r[0]['dimensions']={'closure':2}
    r[0]['reasons']=[{'code':'INCOMPLETE_PAYOFF','confirmed_by':'human'}]
    r[0]['relative_assessment']={'comparison_set_id':'relative-set','confirmed_by':'human','preferred_candidate_id':'0',
        'alternatives':[{'candidate_id':'0','candidate_version':1},{'candidate_id':'1','candidate_version':1}], 'all_options_below_bar':True}
    report=evaluate_pool(r,{})
    assert report['problem_dimensions']['closure']['evaluated']==1
    assert report['problem_dimensions']['closure']['problem_count']==1
    assert report['relative_preferences']['all_options_below_bar']==1
    assert report['precision_at_3']==0 and report['acceptance_at_3_clean']==0


def test_administrative_queries_are_audited_separately_from_editorial_coverage():
    from app.editorial_dataset import evaluate_pool
    regular=rows([3]);admin=rows([0]);admin[0].update(candidate_id='admin',comparison_set_id='admin-pool',administrative=True)
    report=evaluate_pool(regular+admin,{})
    assert report['queries_generated']==1 and report['excluded_administrative_queries']==1
    assert report['acceptance_at_3_clean']==pytest.approx(1/3)
