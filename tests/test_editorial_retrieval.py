import copy,json
import pytest


def policy():return {'status':'APPROVED','brief_sha256':'b'*64,'brief':{'status':'APPROVED','scope':'GTA_VI'}}
def dataset():
    rows=[]
    for i,(grade,decision) in enumerate(((3,'APPROVED'),(0,'REJECTED'),(None,'APPROVED_WITH_ADJUSTMENTS'),(3,'APPROVED'))):
        rows.append({'candidate_id':f'candidate{i}','artifact_id':'sha256:'+'a'*64,'source_group_id':f'family{i}',
            'job_id':f'job{i}','source_fingerprint':str(i)*64,'split':'train','human_confirmed':True,'authorized':True,
            'content_grade':grade,'decision':decision,'text':'GTA discovery proof','comment_raw':'SYNTHETIC review',
            'versions':{'brief_sha256':'b'*64}})
    return {'manifest':{'dataset_id':'d'*64,'records_sha256':'fixture'},'records':rows}
def query():return {'source_group_id':'new-source','source_fingerprint':'f'*64,'text':'GTA discovery proof'}
def budget():return {'context_window':4096,'generation_reserve':700,'context_tokens_upper_bound':1000,'max_example_tokens':600}


def test_retrieval_excludes_same_source_and_holdout():
    from app.editorial_retrieval import select_examples
    data=dataset();data['records'][1]['split']='test';data['records'][2]['human_confirmed']=False
    q=query();q['source_fingerprint']='0'*64
    result=select_examples(q,data,policy(),budget())
    assert [r['candidate_id'] for r in result]==['candidate3']


def test_three_examples_diverse_within_budget():
    from app.editorial_retrieval import select_examples
    data=dataset();data['records'][3]['source_group_id']='family0'
    result=select_examples(query(),data,policy(),budget())
    assert len(result)==3
    assert len({r['source_group_id'] for r in result})==3
    assert {r['category'] for r in result}=={'positive','negative','conditional'}
    assert len(json.dumps([r['prompt_data'] for r in result],ensure_ascii=False).encode())<=600


def test_no_eligible_examples_uses_brief_only_and_preserves_full_examples():
    from app.editorial_retrieval import select_examples,retrieval_snapshot
    data=dataset()
    for row in data['records']:row['human_confirmed']=False
    assert select_examples(query(),data,policy(),budget())==[]
    result=retrieval_snapshot(query(),data,policy(),budget())
    assert result['reason']=='NO_ELIGIBLE_EXAMPLES' and result['examples']==[]
    data=dataset()
    for row in data['records']:row['comment_raw']='x'*5000
    assert select_examples(query(),data,policy(),budget())==[]  # never slice a human comment
    assert select_examples(query(),dataset(),{'status':'NONE'},budget())==[]


def test_prompt_drops_examples_before_source_or_generation_reserve():
    from app.editorial_retrieval import select_examples,append_prompt_examples
    examples=select_examples(query(),dataset(),policy(),budget())
    base='Source closing proof '+('x'*3200)
    prompt,used=append_prompt_examples(base,examples,context_window=4096,reserve=450)
    assert prompt.startswith(base) and not used
    small,used=append_prompt_examples('Source closing proof',examples,context_window=4096,reserve=450)
    assert used and 'Source closing proof' in small and 'DADOS' in small


def test_job_freezes_retrieval_and_refuses_changed_context(monkeypatch):
    from app import editorial_retrieval as retrieval
    data=dataset();calls=[]
    monkeypatch.setattr(retrieval,'load_dataset',lambda ident: calls.append(ident) or data)
    job={'id':'new-job','settings':{'retrieval_mode':'lexical','retrieval_dataset_id':'d'*64},
         'source_fingerprint':'f'*64,'editorial_policy':policy()}
    segments=[{'text':'GTA discovery proof'}]
    saved=retrieval.prepare_job_retrieval(job,segments)
    job['retrieval_snapshot']=copy.deepcopy(saved)
    assert retrieval.prepare_job_retrieval(job,segments)==saved and len(calls)==1
    with pytest.raises(ValueError,match='context'):retrieval.prepare_job_retrieval(job,[{'text':'changed'}])


def test_retrieval_settings_are_opt_in_and_snapshotted():
    from app.job_settings import normalize_job_settings
    assert normalize_job_settings()['retrieval_mode']=='off'
    enabled=normalize_job_settings({'editorial_protocol':2,'retrieval_mode':'lexical','retrieval_dataset_id':'d'*64})
    assert enabled['retrieval_dataset_id']=='d'*64
    with pytest.raises(ValueError):normalize_job_settings({'retrieval_mode':'lexical','retrieval_dataset_id':'../unsafe'})


def test_ranker_and_director_receive_frozen_examples_with_complete_source(monkeypatch):
    from app import ranker,director
    from app.editorial_retrieval import select_examples
    examples=select_examples(query(),dataset(),policy(),budget());seen=[];events=[]
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'response':json.dumps({'ranked':[{'index':0}], 'hook':'Discovery','effects':[],'broll':[]})}).encode()
    def respond(request,**kwargs):seen.append(json.loads(request.data)['prompt']);return Reply()
    monkeypatch.setattr(ranker.urllib.request,'urlopen',respond)
    clip={'start':0,'end':20,'score':1,'text':'GTA discovery proof. COMPLETE SOURCE END.'}
    ranker.rerank_with_ollama([clip],examples=examples,on_event=lambda event,details:events.append((event,details)))
    director.direct_edit({**clip,'retrieval_snapshot':{'examples':examples}}, {},mode='ollama')
    assert len(seen)==2 and all('SYNTHETIC review' in prompt and 'COMPLETE SOURCE END.' in prompt for prompt in seen)
    assert any(event=='retrieval_context' and detail['used_candidate_ids'] for event,detail in events)
