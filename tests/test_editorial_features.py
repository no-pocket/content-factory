import pytest

def test_features_are_predecision_bounded_and_missing_is_explicit():
    from app.editorial_features import extract_features
    a=extract_features({'text':'Synthetic story','source_range':{'start':20,'end':30}}, {'duration':10},
                       {'llm_relevance':.8,'content_grade':3,'decision':'APPROVED'}, {'schema':'fixture'})
    b=extract_features({'text':'Synthetic story','source_range':{'start':20,'end':30}}, {'duration':10},
                       {'llm_relevance':.8,'content_grade':0,'decision':'REJECTED'}, {'schema':'fixture'})
    assert a==b and len(a['values'])<=12
    assert 'content_grade' not in a['values'] and a['missing']['pause_fraction'] is True
    assert a['values']['duration_seconds']==10
    with pytest.raises(ValueError):extract_features({}, {}, {'llm_relevance':float('nan')},{})
