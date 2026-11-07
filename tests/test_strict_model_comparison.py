import copy
import io
import json
import pytest


def transcript():
    return {'language': 'pt', 'segments': [
        {'start': i*10, 'end': (i+1)*10, 'text': 'GTA VI mostra mapa de Vice City.',
         'words': [{'start': i*10, 'end': i*10+1, 'text': 'GTA'}]} for i in range(6)]}


def plan():
    return {'clips': [dict(start_segment=2*i, end_segment=2*i+1, rank=i+1,
        reason='Mapa apresentado com conclusão.', hook='Mapa de Vice City', effects=[], broll=[],
        story={'closure':'COMPLETE','evidence':[{'segment_id':2*i+1,'quote':'GTA VI mostra mapa de Vice City.'}],
               'parts':{'hook':None,'setup':None,'proof':2*i+1,'payoff':2*i+1}}) for i in range(3)]}


def test_strict_plan_uses_only_model_spans_titles_and_source_times():
    from research.strict_model_comparison import validate_model_plan
    original=transcript();before=copy.deepcopy(original)
    result=validate_model_plan(plan(), original, 60)
    assert [(c['start'],c['end']) for c in result]==[(0,20),(20,40),(40,60)]
    assert all(c['timeline']['layers']['text'][0]['text']=='Mapa de Vice City' for c in result)
    assert all(c['model_story']['closure']=='COMPLETE' for c in result)
    assert original==before


@pytest.mark.parametrize('mutation', ['missing','float_id','overlap','duration','title','evidence','path','effect'])
def test_strict_plan_never_fills_or_silently_repairs_invalid_model_output(mutation):
    from research.strict_model_comparison import validate_model_plan
    candidate=plan()
    if mutation=='missing':candidate['clips'].pop()
    if mutation=='float_id':candidate['clips'][0]['start_segment']=0.0
    if mutation=='overlap':candidate['clips'][1]['start_segment']=0
    if mutation=='duration':candidate['clips'][0]['end_segment']=0
    if mutation=='title':candidate['clips'][0]['hook']='Rockstar confirmou amanhã'
    if mutation=='evidence':candidate['clips'][0]['story']['evidence'][0]['quote']='Inventado'
    if mutation=='path':candidate['clips'][0]['file']='evil.mp4'
    if mutation=='effect':candidate['clips'][0]['effects']=[{'type':'exec','at':1}]
    with pytest.raises(ValueError):validate_model_plan(candidate,transcript(),60)


def test_reasoning_must_close_and_json_must_be_complete():
    from research.strict_model_comparison import parse_model_plan
    encoded=json.dumps(plan())
    assert parse_model_plan('<think>provider output</think>\n'+encoded)==plan()
    for bad in ('<think>unfinished '+encoded, encoded+' trailing',encoded[:-3]):
        with pytest.raises(ValueError):parse_model_plan(bad)


@pytest.mark.parametrize('problem',['parts','ending','short_word','long_title','empty_evidence','missing_evidence'])
def test_direct_contract_is_as_strict_as_staged_contract(problem):
    from research.strict_model_comparison import validate_model_plan,bind_model_evidence
    value=plan();item=value['clips'][0]
    if problem=='parts':item['story'].pop('parts')
    if problem=='ending':
        item['story'].update(closure='UNCERTAIN',evidence=[{'segment_id':0,'quote':'GTA VI mostra mapa de Vice City.'}])
        item['story']['parts']={key:None for key in ('hook','setup','proof','payoff')}
    if problem=='short_word':item['hook']='Mapa FBI de Vice City'
    if problem=='long_title':item['hook']='Mapa de Vice City GTA VI mostra mapa City'
    if problem=='empty_evidence':item['story']['evidence']=[]
    if problem=='missing_evidence':item['story'].pop('evidence')
    with pytest.raises(ValueError):
        if problem in ('empty_evidence','missing_evidence'):bind_model_evidence(item,transcript())
        else:validate_model_plan(value,transcript(),60)


@pytest.mark.parametrize('problem',['engine','provenance','inputs','language'])
def test_wrong_producer_envelope_fails_before_new_job(tmp_path,monkeypatch,problem):
    from research.run_strict_comparison import render
    from app import store
    task={'transcript':transcript(),'prompt_sha256':'prompt','source_sha256':'source',
          'transcript_file_sha256':'transcript','source_job':{'source':'/data/input/source.mp4','duration':60,
          'original_name':'source','creator':'creator','license_note':'authorized'}}
    decision={'engine':'hermes','language':'pt','plan':plan(),
              'inputs':{key:task[key] for key in ('source_sha256','transcript_file_sha256','prompt_sha256')},
              'provenance':{'process':'hermes_mcp_full_editorial_plan','heuristic_used':False,
                            'common_source_prompt_sha256':'prompt','message_ids':['message'],
                            'model_identity_verified':False}}
    if problem=='engine':decision['engine']='qwen'
    if problem=='provenance':decision.pop('provenance')
    if problem=='inputs':decision['inputs']['source_sha256']='wrong'
    if problem=='language':decision['language']='en'
    (tmp_path/'tasks').mkdir();(tmp_path/'hermes'/'pt').mkdir(parents=True)
    (tmp_path/'tasks'/'pt.json').write_text(json.dumps(task))
    (tmp_path/'hermes'/'pt'/'validated-plan.json').write_text(json.dumps(decision))
    monkeypatch.setattr(store,'new_job',lambda *a,**k:pytest.fail('Must reject before persisting QUEUED'))
    with pytest.raises(ValueError):render(tmp_path,'hermes','pt')


def test_common_prompt_keeps_full_transcript_without_word_metadata():
    from research.strict_model_comparison import build_plan_prompt
    source=transcript()
    source['segments'][-1]['text']='FINAL SOURCE EVIDENCE'
    prompt=build_plan_prompt(source,60)
    assert 'FINAL SOURCE EVIDENCE' in prompt
    assert 'word_id' not in prompt
    assert '[5,50,60,' in prompt
    assert 'exactly 3' in prompt


def test_native_schema_binds_evidence_to_source_and_limits_segment_ids():
    import jsonschema
    from research.strict_model_comparison import model_plan_schema
    schema=model_plan_schema(transcript())
    jsonschema.validate(plan(),schema)
    invalid=plan();invalid['clips'][0]['end_segment']=900
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(invalid,schema)
    invalid=plan();invalid['clips'][0]['story']['evidence'][0]['quote']='Inventado'
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(invalid,schema)


def test_staged_selection_preserves_model_ranks_and_rejects_invented_ids():
    from research.strict_model_comparison import validate_model_spans
    selection={'clips':[{k:c[k] for k in ('start_segment','end_segment','rank','reason')} for c in plan()['clips']]}
    assert validate_model_spans(selection,transcript(),60)==selection['clips']
    selection['clips'][1]['start_segment']=900
    with pytest.raises(ValueError,match='IDs'):validate_model_spans(selection,transcript(),60)


def test_model_evidence_ids_are_resolved_by_exact_source_lookup_not_invented_quotes():
    from research.strict_model_comparison import bind_model_evidence
    direction=copy.deepcopy(plan()['clips'][0]);direction['story']['evidence']=[{'segment_id':1}]
    bound=bind_model_evidence(direction,transcript())
    assert bound['story']['evidence'][0]['quote']==transcript()['segments'][1]['text']
    assert 'quote' not in direction['story']['evidence'][0]
    direction['story']['evidence']=[{'segment_id':1,'quote':'Invented quote must not be repaired'}]
    assert bind_model_evidence(direction,transcript())['story']['evidence'][0]['quote']=='Invented quote must not be repaired'


def test_valid_source_pair_catalog_does_not_rank_or_choose_content():
    from research.strict_model_comparison import valid_source_pairs,decode_source_pairs
    catalog=valid_source_pairs(transcript(),60)
    assert catalog['0:1']==(0,1) and catalog['0:3']==(0,3)
    assert '0:0' not in catalog and '0:4' not in catalog
    raw={'clips':[{'source_pair':f'{i*2}:{i*2+1}','rank':i+1,'reason':'model choice'} for i in range(3)]}
    decoded=decode_source_pairs(raw,catalog)
    assert [(x['start_segment'],x['end_segment']) for x in decoded['clips']]==[(0,1),(2,3),(4,5)]
    raw['clips'][0]['source_pair']='0:4'
    with pytest.raises(ValueError):decode_source_pairs(raw,catalog)


def test_evidence_materializes_model_parts_and_model_selected_ending():
    from research.strict_model_comparison import bind_model_evidence
    item=copy.deepcopy(plan()['clips'][0]);item['story']['evidence']=[{'segment_id':0}]
    item['story']['parts']['payoff']=1
    result=bind_model_evidence(item,transcript())
    assert [e['segment_id'] for e in result['story']['evidence']]==[0,1]
    assert result['story']['evidence'][1]['quote']==transcript()['segments'][1]['text']
    assert item['story']['evidence']==[{'segment_id':0}]


def test_canonical_title_is_exactly_the_words_chosen_by_model():
    from research.strict_model_comparison import canonical_model_direction
    span={k:plan()['clips'][0][k] for k in ('start_segment','end_segment','rank','reason')}
    raw={k:copy.deepcopy(plan()['clips'][0][k]) for k in ('effects','broll','story')}
    raw['title_words']=['Mapa','de','Vice','City']
    result=canonical_model_direction(span,raw,transcript())
    assert result['hook']=='Mapa de Vice City'
    assert raw['title_words']==['Mapa','de','Vice','City']
    raw['title_words']=['Inventado','City']
    with pytest.raises(ValueError):canonical_model_direction(span,raw,transcript())


def test_external_replay_is_explicit_and_cannot_fall_through_to_worker_heuristic(monkeypatch):
    from app.job_settings import normalize_job_settings
    from app import worker
    settings=normalize_job_settings({'ranker_mode':'external','director_mode':'external',
                                     'llm_backend':'external','llm_model':'external'})
    job={'id':'strict-test','status':'QUEUED','settings':settings,'candidates':[]}
    monkeypatch.setattr(worker,'load',lambda jid:job)
    monkeypatch.setattr(worker,'save',lambda j:None)
    monkeypatch.setattr(worker,'propose_clips',lambda *a,**k:pytest.fail('heuristics forbidden'))
    worker.process('strict-test')
    assert job['status']=='FAILED'
    assert 'external' in str(job['error']).lower()


def test_director_compacts_metadata_without_dropping_any_source_text(monkeypatch):
    from app.director import direct_edit
    from app.editorial_context import build_candidate_context
    original=transcript()
    for i,s in enumerate(original['segments']):
        s['text']=('GTA VI mapa ' * 12)+f'COMPLETE_END_{i}'
        s['words']=[{'start':i*10+k*.1,'end':i*10+(k+1)*.1,'text':'palavra'} for k in range(90)]
    context=build_candidate_context({'candidates':[{'start':20,'end':40}]},0,original)
    stored=copy.deepcopy(context);seen=[]
    def response(request,**kwargs):
        seen.append(json.loads(request.data)['prompt'])
        return io.BytesIO(b'{"response":"{\\"hook\\":\\"Mapa GTA\\",\\"effects\\":[],\\"broll\\":[]}","done_reason":"stop"}')
    monkeypatch.setattr('app.director.urllib.request.urlopen',response)
    hints,engine=direct_edit({'start':20,'end':40,'text':context['text'],'editorial_context':context}, {},mode='ollama',llm_backend='kepler_gpu')
    assert engine=='kepler_gpu'
    assert len(seen)==1
    assert all(f'COMPLETE_END_{i}' in seen[0] for i in range(6))
    assert 'word_id' not in seen[0]
    assert context==stored
