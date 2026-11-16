import pytest
from app.editorial_plan import transcript_digest, segment_id, parse_plan

def test_canonical_transcript_identity_preserves_order_and_unicode():
    a={'language':'pt','segments':[{'start':0.0,'end':1.0,'text':'ol\u00e1','words':[]}]}
    assert transcript_digest(a) == 'sha256:' + __import__('app.artifacts',fromlist=['digest']).digest(a)
    assert transcript_digest(a) != transcript_digest({**a,'language':'en'})
    assert segment_id(0) == 'seg-000000'

def test_strict_parser_rejects_duplicate_keys_and_oversize():
    with pytest.raises(ValueError): parse_plan(b'{"a":1,"a":2}')
    with pytest.raises(ValueError): parse_plan(b' ' * (256*1024+1))

def test_editorial_outcomes_and_identity_validation():
    from app.editorial_plan import validate_editorial_plan
    import uuid
    ids=[str(uuid.uuid4()) for _ in range(5)]
    transcript={'language':'pt','segments':[{'start':0.0,'end':10.0,'text':'Uma fala completa.','words':[]}]}
    request={'job_id':ids[0],'run_id':ids[1],'request_id':ids[2],'editorial_attempt_id':ids[3], 'source_fingerprint':'a'*64,'duration_ms':10000,'transcript_digest':transcript_digest(transcript),'min_seconds':1,'max_seconds':20}
    plan={'schema_version':'1.0',**{k:request[k] for k in ('job_id','run_id','request_id','editorial_attempt_id')},'submission_id':ids[4], 'source':{'source_fingerprint':'a'*64,'duration_ms':10000},'transcript':{'digest':request['transcript_digest'],'canonicalization':'cf-transcript-v1','language':'pt','timebase':'source_ms'},'planner':{'engine':'hermes','provider':'UNKNOWN','model':'UNKNOWN','prompt_version':'v1','invocation_id':'UNKNOWN'},'outcome':'no_suitable_candidates','reason':'Nao ha cortes adequados','candidates':[]}
    assert validate_editorial_plan(plan,request,transcript)['outcome']=='no_suitable_candidates'
    altered={**plan,'source':{**plan['source'],'source_fingerprint':'b'*64}}
    with pytest.raises(ValueError): validate_editorial_plan(altered,request,transcript)
    with pytest.raises(ValueError): validate_editorial_plan({**plan,'outcome':'candidates_proposed'},request,transcript)

def test_candidate_anchors_and_bounds():
    from app.editorial_plan import validate_editorial_plan
    import uuid, copy
    ids=[str(uuid.uuid4()) for _ in range(6)]
    transcript={'language':'pt','segments':[{'start':0.0,'end':5.0,'text':'Primeiro trecho.','words':[]},{'start':5.0,'end':10.0,'text':'Conclusao aqui.','words':[]}]}
    request={'job_id':ids[0],'run_id':ids[1],'request_id':ids[2],'editorial_attempt_id':ids[3], 'source_fingerprint':'a'*64,'duration_ms':10000,'transcript_digest':transcript_digest(transcript),'min_seconds':1,'max_seconds':20, 'layout_presets':['legacy'],'subtitle_presets':['default']}
    candidate={'proposal_id':ids[5],'editorial_title':'Titulo','intent':'Resumo','segments':[{'source_in_ms':0,'source_out_ms':10000,'start_anchor':{'segment_id':'seg-000000','quote':'Primeiro trecho.'},'end_anchor':{'segment_id':'seg-000001','quote':'Conclusao aqui.'},'boundary_status':'requires_audio_review'}],'direction':{'layout_preset_id':'legacy','subtitle_preset_id':'default','pacing':'natural','word_highlight':'only_if_word_timing_reliable'},'risks':[]}
    plan={'schema_version':'1.0',**{k:request[k] for k in ('job_id','run_id','request_id','editorial_attempt_id')},'submission_id':ids[4],'source':{'source_fingerprint':'a'*64,'duration_ms':10000},'transcript':{'digest':request['transcript_digest'],'canonicalization':'cf-transcript-v1','language':'pt','timebase':'source_ms'},'planner':{'engine':'hermes','provider':'UNKNOWN','model':'UNKNOWN','prompt_version':'v1','invocation_id':'UNKNOWN'},'outcome':'candidates_proposed','candidates':[candidate]}
    assert validate_editorial_plan(plan,request,transcript)['candidates'][0]['proposal_id']==ids[5]
    for mutate in ('outside','quote','bool','extra','duplicate'):
        invalid=copy.deepcopy(plan); c=invalid['candidates'][0]
        if mutate=='outside': c['segments'][0]['source_out_ms']=10001
        if mutate=='quote': c['segments'][0]['end_anchor']['quote']='texto inventado'
        if mutate=='bool': c['segments'][0]['source_in_ms']=True
        if mutate=='extra': c['shell_command']='bad'
        if mutate=='duplicate': invalid['candidates'].append(copy.deepcopy(c))
        with pytest.raises(ValueError): validate_editorial_plan(invalid,request,transcript)

def test_editorial_json_schema_validates_both_outcomes():
    import json,uuid
    from pathlib import Path
    from jsonschema import Draft202012Validator
    schema=json.loads((Path(__file__).resolve().parents[1]/'contracts/editorial-plan-v1.schema.json').read_text(encoding='utf8'))
    Draft202012Validator.check_schema(schema)
    ident=lambda:str(uuid.uuid4())
    empty={'schema_version':'1.0','request_id':ident(),'submission_id':ident(),'editorial_attempt_id':ident(),'job_id':ident(),'run_id':ident(),'source':{'source_fingerprint':'a'*64,'duration_ms':10000},'transcript':{'digest':'sha256:'+'b'*64,'canonicalization':'cf-transcript-v1','language':'pt','timebase':'source_ms'},'planner':{'engine':'hermes','provider':'UNKNOWN','model':'UNKNOWN','prompt_version':'v1','invocation_id':'UNKNOWN'},'outcome':'no_suitable_candidates','reason':'Nenhum corte','candidates':[]}
    validator=Draft202012Validator(schema)
    assert not list(validator.iter_errors(empty))
    candidate={'proposal_id':ident(),'editorial_title':'Titulo','intent':'Motivo','segments':[{'source_in_ms':0,'source_out_ms':10000,'start_anchor':{'segment_id':'seg-000000','quote':'Inicio'},'end_anchor':{'segment_id':'seg-000001','quote':'Fim'},'boundary_status':'requires_audio_review'}],'direction':{'layout_preset_id':'legacy','subtitle_preset_id':'bold_karaoke_v1','pacing':'natural','word_highlight':'only_if_word_timing_reliable'},'risks':[]}
    proposed={k:v for k,v in empty.items() if k!='reason'};proposed.update(outcome='candidates_proposed',candidates=[candidate])
    assert not list(validator.iter_errors(proposed))
    assert list(validator.iter_errors({**proposed,'candidates':[]}))
    assert list(validator.iter_errors({**empty,'extra':'bad'}))
