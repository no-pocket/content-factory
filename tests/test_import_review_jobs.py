import hashlib
import json
import uuid
from pathlib import Path
import pytest
from app.artifacts import digest


def fixture(tmp_path):
    from app.editorial_contracts import candidate_key
    source=tmp_path/'baseline';target=tmp_path/'main';jid=str(uuid.uuid4());cid=candidate_key(jid,0)
    for folder in (source/'work',source/'output'/jid/cid/'render_1',target/'input'):
        folder.mkdir(parents=True)
    (target/'input'/'source.mp4').write_bytes(b'authorized source')
    manifest={'candidate_id':cid,'candidate_version':1,'render_revision':1,
              'plan_sha256':digest({'start':None,'end':None,'timeline':None}),'files':{}}
    for kind,name in [('mp4','master.mp4'),('webm','master.preview.webm'),('timeline','master.timeline.json')]:
        data=(kind+' content').encode();path=source/'output'/jid/cid/'render_1'/name;path.write_bytes(data)
        manifest['files'][kind]={'path':f'{cid}/render_1/{name}','sha256':hashlib.sha256(data).hexdigest()}
    job={'id':jid,'source':'/observed/input/source.mp4','status':'NEEDS_REVIEW','source_parent_job':'parent',
         'candidates':[{'file':f'/batch/data/output/{jid}/{cid}/render_1/master.mp4',
            'timeline_file':f'/batch/data/output/{jid}/{cid}/render_1/master.timeline.json',
            'artifact_manifest':manifest,'artifact_id':'sha256:'+digest(manifest)}],
         'source_fingerprint':hashlib.sha256(b'authorized source').hexdigest(),
         'decision_history':[{'comment':'/batch/data/private human wording'}]}
    (source/'work'/(jid+'.json')).write_text(json.dumps(job))
    (source/'work'/(jid+'.transcript.json')).write_text('{"segments":[]}')
    return source,target,job


def test_import_rebases_storage_preserves_artifact_identity_and_existing_feedback(tmp_path):
    from research.import_review_jobs import import_review_job
    source,target,job=fixture(tmp_path)
    result=import_review_job(source,target,job['id'])
    imported=json.loads((target/'work'/(job['id']+'.json')).read_text())
    assert result['state']=='IMPORTED'
    assert imported['source']=='/data/input/source.mp4'
    assert imported['candidates'][0]['file'].startswith('/data/output/')
    assert imported['candidates'][0]['artifact_id']==job['candidates'][0]['artifact_id']
    assert imported['decision_history']==job['decision_history']
    imported['decision_history']=[{'comment':'Feedback humano preservado'}]
    (target/'work'/(job['id']+'.json')).write_text(json.dumps(imported))
    assert import_review_job(source,target,job['id'])['state']=='ALREADY_PRESENT'
    assert json.loads((target/'work'/(job['id']+'.json')).read_text())['decision_history']==imported['decision_history']


@pytest.mark.parametrize('problem',['escape','corrupt'])
def test_import_rejects_escaping_or_corrupt_artifacts(tmp_path,problem):
    from research.import_review_jobs import import_review_job
    source,target,job=fixture(tmp_path)
    entry=job['candidates'][0]['artifact_manifest']['files']['mp4']
    if problem=='escape':entry['path']='../../outside.mp4'
    else:(source/'output'/job['id']/entry['path']).write_bytes(b'corrupt')
    (source/'work'/(job['id']+'.json')).write_text(json.dumps(job))
    with pytest.raises(ValueError):import_review_job(source,target,job['id'])
    assert not (target/'work'/(job['id']+'.json')).exists()


@pytest.mark.parametrize('problem',['pointer','timeline','history','input','fingerprint','plan'])
def test_import_rejects_inconsistent_storage_and_identity(tmp_path,problem):
    from research.import_review_jobs import import_review_job
    source,target,job=fixture(tmp_path);clip=job['candidates'][0]
    if problem=='pointer':clip['file']='/batch/data/output/'+job['id']+'/wrong.mp4'
    if problem=='timeline':clip['timeline_file']='/batch/data/output/'+job['id']+'/wrong.timeline.json'
    if problem=='history':clip['render_history']=[{'artifact_manifest':clip['artifact_manifest'],'artifact_id':'sha256:wrong'}]
    if problem=='input':
        (target/'outside.mp4').write_bytes(b'authorized source');job['source']='/data/input/../outside.mp4'
    if problem=='fingerprint':job['source_fingerprint']='0'*64
    if problem=='plan':clip['timeline']={'changed':True}
    (source/'work'/(job['id']+'.json')).write_text(json.dumps(job))
    with pytest.raises(ValueError):import_review_job(source,target,job['id'])
    assert not (target/'work'/(job['id']+'.json')).exists()


def test_interrupted_copy_can_retry_without_replacing_preexisting_file(tmp_path,monkeypatch):
    from research import import_review_jobs as module
    source,target,job=fixture(tmp_path);unrelated=target/'input'/'keep.txt';unrelated.write_text('keep')
    original=module.shutil.copyfileobj
    def interrupt(reader,writer):
        writer.write(reader.read(2));raise OSError('synthetic interruption')
    monkeypatch.setattr(module.shutil,'copyfileobj',interrupt)
    with pytest.raises(OSError):module.import_review_job(source,target,job['id'])
    monkeypatch.setattr(module.shutil,'copyfileobj',original)
    assert module.import_review_job(source,target,job['id'])['state']=='IMPORTED'
    assert unrelated.read_text()=='keep'


@pytest.mark.parametrize('problem',['pointer','bytes'])
def test_idempotent_import_detects_main_corruption_without_overwriting_feedback(tmp_path,problem):
    from research.import_review_jobs import import_review_job
    source,target,job=fixture(tmp_path);import_review_job(source,target,job['id'])
    record=target/'work'/(job['id']+'.json');existing=json.loads(record.read_text())
    existing['decision_history']=[{'comment':'preserve'}]
    if problem=='pointer':existing['candidates'][0]['file']='/data/output/'+job['id']+'/wrong.mp4'
    else:(target/'output'/job['id']/existing['candidates'][0]['artifact_manifest']['files']['mp4']['path']).write_bytes(b'changed')
    record.write_text(json.dumps(existing));before=record.read_bytes()
    with pytest.raises((ValueError,FileExistsError)):import_review_job(source,target,job['id'])
    assert record.read_bytes()==before
