import pytest
from research.ollama_reasoning_plans import finished_decision


def test_r1_requires_completed_reasoning_and_complete_json():
    response={'done':True,'done_reason':'stop','thinking':'nonempty model output','response':'{"clips":[]}'}
    assert finished_decision(response)=={'clips':[]}
    for change in ({'done_reason':'length'},{'thinking':''},{'response':'{"clips":['},{'done':False}):
        with pytest.raises(ValueError):finished_decision({**response,**change})


def test_remaining_pairs_only_filters_overlap_with_model_choices():
    from research.ollama_reasoning_plans import remaining_source_pairs
    catalog={'0:2':(0,2),'1:3':(1,3),'3:5':(3,5),'6:8':(6,8)}
    assert remaining_source_pairs(catalog,[])==catalog
    selected=[{'start_segment':1,'end_segment':3}]
    assert remaining_source_pairs(catalog,selected)=={'6:8':(6,8)}


def test_native_reasoning_rejects_length_and_quoted_terminator():
    from research.ollama_reasoning_plans import finished_native_reasoning
    good={'done':True,'done_reason':'stop','response':'Actual reasoning.\n</think>\n{"clips":[]}'}
    assert finished_native_reasoning(good)=='Actual reasoning.\n'
    for change in ({'done_reason':'length'},{'response':'The marker "</think>" is needed.'},
                   {'response':'Quoted example:\n```\n</think>\n```\nStill reasoning.'},{'done':False}):
        with pytest.raises(ValueError):finished_native_reasoning({**good,**change})


def test_unconstrained_draft_is_not_the_accepted_final_decision():
    from research.ollama_reasoning_plans import finished_native_reasoning
    first={'done':True,'done_reason':'stop','response':'Actual reasoning.\n</think>\n```json\n{invalid draft}\n```'}
    assert finished_native_reasoning(first)=='Actual reasoning.\n'
    with pytest.raises(ValueError):finished_decision({**first,'thinking':'trace','response':'{invalid draft}'})
