import copy
import uuid
import pytest
from test_editorial_contracts import feedback


def job(label='a',grade=3):
    from app.editorial_contracts import candidate_key
    jid=str(uuid.uuid5(uuid.NAMESPACE_URL,label));cid=candidate_key(jid,0)
    event=feedback();event.update(job_id=jid,candidate_id=cid,decision='APPROVED',comment_raw='SYNTHETIC confirmed review',content_grade=grade)
    return {'id':jid,'creator':'QA','license_note':'Synthetic grant','source_fingerprint':label*64 if len(label)==1 and label in 'abcdef' else None,
            'language':'en','editorial_protocol':2,'candidates':[{'candidate_id':cid,'start':0,'end':10,'state':'VALID','text':'Synthetic complete story',
            'artifact_id':event['artifact_id'],'candidate_version':1,'render_revision':1}], 'feedback_events':[event]}


def config(**extra):
    return {'cutoff':'2026-11-08T00:00:00Z','seed':17,**extra}


def test_aliases_and_retries_never_cross_split():
    from app.editorial_dataset import build_dataset
    a,b,c=job('a'),job('b'),job('c');b['source_parent_job']=a['id'];c['source_fingerprint']=b['source_fingerprint']
    d=build_dataset([a,b,c],config(),None)
    assert len({r['source_group_id'] for r in d['records']})==1
    assert len({r['split'] for r in d['records']})==1


def test_admin_and_unconfirmed_legacy_have_no_absolute_target():
    from app.editorial_dataset import build_dataset
    a,b=job('a'),job('b');a['editorial_protocol']=1;a.pop('feedback_events');a.update(status='APPROVED',approved=[0])
    b['feedback_events'][0].update(decision='REJECTED',rejection_domain='ADMINISTRATIVE')
    d=build_dataset([a,b],config(),None)
    assert all(r['content_grade'] is None and r['release_ready'] is None for r in d['records'])
    assert d['manifest']['eligible_content_candidates']==0


def test_duplicate_request_counts_once_and_cutoff_is_enforced():
    from app.editorial_dataset import build_dataset
    a=job();a['feedback_events']*=2
    late=copy.deepcopy(a['feedback_events'][0]);late.update(request_id=str(uuid.uuid4()),event_id=str(uuid.uuid4()),created_at='2026-11-09T00:00:00Z',editorial_revision=2,content_grade=0)
    a['feedback_events'].append(late)
    result=build_dataset([a],config(),None)
    assert len(result['records'])==1 and result['records'][0]['content_grade']==3
    assert result['manifest']['human_events_before_cutoff']==1


def test_snapshot_change_aborts_export(tmp_path):
    from app.editorial_dataset import build_dataset
    with pytest.raises(ValueError,match='snapshot'):
        build_dataset([job()],config(dry_run=False,export_root=str(tmp_path),snapshot_reader=lambda: {'changed':'a'}),tmp_path/'snapshot')
    assert not (tmp_path/'snapshot').exists()


def test_export_is_immutable_deterministic_and_contains_no_media_paths(tmp_path):
    from app.editorial_dataset import build_dataset
    a=job();a['source']='/private/input.mp4';a['api_token']='must-not-export'
    first=build_dataset([a],config(),None);second=build_dataset([a],config(),None)
    assert first==second
    import json
    raw=json.dumps(first)
    assert '/private' not in raw and 'must-not-export' not in raw
    written=build_dataset([a],config(dry_run=False,export_root=str(tmp_path)),tmp_path/'one')
    assert (tmp_path/'one/manifest.json').is_file()
    assert written['manifest']['dataset_id']==first['manifest']['dataset_id']
    with pytest.raises(FileExistsError):build_dataset([a],config(dry_run=False,export_root=str(tmp_path)),tmp_path/'one')
    with pytest.raises(ValueError):build_dataset([a],config(dry_run=False,export_root=str(tmp_path/'safe')),tmp_path/'escape')


def test_old_artifact_and_conflicting_duplicate_are_not_current_targets():
    from app.editorial_dataset import build_dataset
    a=job();a['candidates'][0]['artifact_id']='sha256:'+'b'*64
    assert build_dataset([a],config(),None)['records'][0]['content_grade'] is None
    a=job();bad=copy.deepcopy(a['feedback_events'][0]);bad['content_grade']=0;a['feedback_events'].append(bad)
    with pytest.raises(ValueError,match='Conflicting'):build_dataset([a],config(),None)
