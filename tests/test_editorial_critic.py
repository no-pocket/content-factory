import copy
import pytest


def context():
    return {'source_range':{'start':0,'end':40},'segments':[
        {'segment_id':0,'source_start':0,'source_end':40,'text':'Synthetic GTA VI source evidence.'}], 'before':[],'after':[]}


def critique():
    return {'schema_version':'1.0','uncertainty':'SYNTHETIC: textual evidence only','suggestions':[
        {'kind':'BOUNDARY','source_start':0,'source_end':40,'reason':'SYNTHETIC: preserve conclusion',
         'evidence':[{'segment_id':0,'quote':'source evidence'}]}]}


@pytest.mark.parametrize('change', ['outside','path','approval','no_evidence','unsupported_quote'])
def test_invalid_critic_cannot_override_timeline_or_review(change):
    from app.editorial_critic import validate_critique
    payload=critique()
    if change=='outside':payload['suggestions'][0]['source_end']=99
    elif change=='path':payload['suggestions'][0]['path']='../../secret'
    elif change=='approval':payload['decision']='APPROVED'
    elif change=='no_evidence':payload['suggestions'][0]['evidence']=[]
    elif change=='unsupported_quote':payload['suggestions'][0]['evidence'][0]['quote']='invented evidence'
    with pytest.raises(ValueError):validate_critique(payload,context())


def test_missing_hermes_capability_keeps_local_direction():
    from app.editorial_critic import critique_plan
    plan={'schema_version':'2.0','source_range':{'start':0,'end':40}}
    before=copy.deepcopy(plan)
    result=critique_plan(context(),plan)
    assert result['baseline']==before and plan==before
    assert result['status']=='UNAVAILABLE'
    assert result['sent'] is False


def test_dry_run_never_calls_transport():
    from app.editorial_critic import critique_plan
    def forbidden(_):pytest.fail('Dry-run transmitted content')
    result=critique_plan(context(),{'source_range':{'start':0,'end':40}},
        capability={'execution':True,'structured_response':True,'vision':False},transport=forbidden,dry_run=True)
    assert not result['sent'] and result['status']=='DRY_RUN'


def test_fake_critique_is_advisory_and_source_anchored():
    from app.editorial_critic import critique_plan
    plan={'source_range':{'start':0,'end':40}}
    result=critique_plan(context(),plan,capability={'execution':True,'structured_response':True,'vision':False},
                         transport=lambda _:critique(),dry_run=False)
    assert result['baseline']==plan
    assert result['critique']['suggestions'][0]['evidence'][0]['source_end']==40
    assert 'decision' not in result
