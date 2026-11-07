"""Import new review jobs without changing render identities or human feedback."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from app.artifacts import digest
from app.editorial_contracts import candidate_key
from app.store import file_lock


def checksum(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def atomic_copy(source,destination,expected):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if checksum(destination)!=expected:raise FileExistsError('Existing main file differs')
        return
    pending=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with source.open('rb') as reader,pending.open('xb') as writer:
            shutil.copyfileobj(reader,writer);writer.flush();os.fsync(writer.fileno())
        if checksum(pending)!=expected:raise ValueError('Staged import hash mismatch')
        if destination.exists():
            if checksum(destination)!=expected:raise FileExistsError('Concurrent main file differs')
        else:os.replace(pending,destination)
    finally:
        pending.unlink(missing_ok=True)


def storage_path(value):
    for old in ('/batch/data/','/observed/'):
        if value.startswith(old):return '/data/'+value[len(old):]
    return value


def candidate_relative(value,jid):
    path=Path(storage_path(value));root=Path('/data/output')/jid
    if '..' in path.parts or not path.is_relative_to(root):raise ValueError('Candidate storage pointer outside job')
    return path.relative_to(root).as_posix()


def import_review_job(source_data: Path,target_data: Path,jid: str) -> dict:
    uuid.UUID(jid)
    record=source_data/'work'/(jid+'.json');job=json.loads(record.read_text(encoding='utf-8'))
    if job['id']!=jid or job['status'] not in ('NEEDS_REVIEW','PARTIAL_FAILED','FAILED','APPROVED','REJECTED'):
        raise ValueError('Only terminal review jobs may be imported')
    source_base=(source_data/'output').resolve();dest_base=(target_data/'output').resolve()
    source_root=(source_base/jid).resolve();dest_root=(dest_base/jid).resolve()
    if not source_root.is_relative_to(source_base) or not dest_root.is_relative_to(dest_base):
        raise ValueError('Job output root escapes output directory')
    source_path=Path(storage_path(job['source']));input_base=(target_data/'input').resolve()
    if '..' in source_path.parts or not source_path.is_relative_to('/data/input'):
        raise ValueError('Imported source outside input directory')
    target_input=(target_data/source_path.relative_to('/data')).resolve()
    if not target_input.is_relative_to(input_base) or not target_input.is_file():
        raise ValueError('Imported source outside resolved input directory')
    if checksum(target_input)!=job.get('source_fingerprint'):raise ValueError('Main source fingerprint mismatch')
    files=[];identities=[]
    for index,clip in enumerate(job['candidates']):
        manifest=clip['artifact_manifest'];identity='sha256:'+digest(manifest)
        if identity!=clip['artifact_id']:raise ValueError('Artifact manifest identity changed')
        plan=digest({key:clip.get(key) for key in ('start','end','timeline')})
        if manifest['plan_sha256']!=plan:raise ValueError('Candidate plan differs from manifest')
        if manifest['candidate_id']!=clip.get('candidate_id',candidate_key(jid,index)) or any(
            manifest[key]!=clip.get(key,1) for key in ('candidate_version','render_revision')):
            raise ValueError('Candidate version identity differs from manifest')
        master=clip.get('file');timeline=clip.get('timeline_file') or (str(Path(master).with_suffix('.timeline.json')) if master else None)
        pointers={'mp4':master,'webm':str(Path(master).with_suffix('.preview.webm')) if master else None,'timeline':timeline}
        for kind,pointer in pointers.items():
            entry=manifest['files'].get(kind)
            if pointer is not None and (entry is None or candidate_relative(pointer,jid)!=entry['path']):
                raise ValueError('Candidate pointer differs from artifact manifest')
        identities.append(identity)
        history=clip.get('render_history',[])
        for previous in history:
            if previous.get('artifact_id')!='sha256:'+digest(previous['artifact_manifest']):
                raise ValueError('Historical artifact identity changed')
        manifests=[manifest]+[h['artifact_manifest'] for h in history]
        for current in manifests:
            for entry in current['files'].values():
                if entry is None:continue
                relative=Path(entry['path']);src=(source_root/relative).resolve();dst=(dest_root/relative).resolve()
                if relative.is_absolute() or '..' in relative.parts or not src.is_relative_to(source_root) or not dst.is_relative_to(dest_root):
                    raise ValueError('Artifact path escapes job directory')
                if not src.is_file() or checksum(src)!=entry['sha256']:raise ValueError('Source artifact hash mismatch')
                files.append((src,dst,entry['sha256']))
    target_work=target_data/'work';target_work.mkdir(parents=True,exist_ok=True);target=target_work/(jid+'.json')
    with file_lock(target_work/(jid+'.lock')):
        if target.exists():
            existing=json.loads(target.read_text())
            if [c.get('artifact_id') for c in existing.get('candidates',[])]!=identities:
                raise FileExistsError('Existing main job differs; never overwrite it')
            for clip in existing['candidates']:
                manifest=clip['artifact_manifest']
                if 'sha256:'+digest(manifest)!=clip['artifact_id'] or manifest['plan_sha256']!=digest({key:clip.get(key) for key in ('start','end','timeline')}):
                    raise FileExistsError('Existing main identity differs')
                master=clip.get('file');timeline=clip.get('timeline_file') or str(Path(master).with_suffix('.timeline.json'))
                pointers={'mp4':master,'webm':str(Path(master).with_suffix('.preview.webm')),'timeline':timeline}
                if any(candidate_relative(pointer,jid)!=manifest['files'][kind]['path'] for kind,pointer in pointers.items()):
                    raise FileExistsError('Existing main storage pointer differs')
            for _,destination,expected in files:
                if not destination.is_file() or checksum(destination)!=expected:raise ValueError('Existing main artifact hash differs')
            return {'id':jid,'state':'ALREADY_PRESENT'}
        for src,dst,expected in files:
            atomic_copy(src,dst,expected)
        migrated=copy.deepcopy(job);migrated['source']=storage_path(job['source'])
        for clip in migrated['candidates']:
            for key in ('file','timeline_file'):
                if clip.get(key):clip[key]=storage_path(clip[key])
            actual=copy.deepcopy(clip['artifact_manifest'])
            actual['plan_sha256']=digest({key:clip.get(key) for key in ('start','end','timeline')})
            for entry in actual['files'].values():
                if entry is not None:entry['sha256']=checksum(dest_root/entry['path'])
            if 'sha256:'+digest(actual)!=clip['artifact_id']:raise ValueError('Imported identity differs')
        migrated['import_provenance']={'source_job_record_sha256':checksum(record),'artifact_ids_preserved':identities}
        transcript=source_data/'work'/(jid+'.transcript.json');target_transcript=target_work/transcript.name
        if transcript.is_file():
            atomic_copy(transcript,target_transcript,checksum(transcript))
        pending=target_work/(jid+'.'+uuid.uuid4().hex+'.tmp')
        pending.write_text(json.dumps(migrated,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(pending,target)
    return {'id':jid,'state':'IMPORTED','candidates':len(job['candidates'])}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-data',type=Path,required=True)
    parser.add_argument('--target-data',type=Path,required=True);parser.add_argument('ids',nargs='+');args=parser.parse_args()
    for jid in args.ids:print(json.dumps(import_review_job(args.source_data,args.target_data,jid)),flush=True)
