"""Deterministic local-only human dataset export and descriptive pool evaluation.

This learning-branch module is never imported by startup or the production worker.
"""
from __future__ import annotations
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import uuid
from .artifacts import digest
from .editorial_contracts import candidate_key,project_legacy_review,validate_feedback_event
from .editorial_features import extract_features


def utc(value):
    date=datetime.fromisoformat(value.replace('Z','+00:00'))
    if date.utcoffset() is None or date.utcoffset().total_seconds()!=0:raise ValueError('UTC cutoff required')
    return date


def input_hashes(jobs):
    result={}
    for job in jobs:
        ident=job['id'];checksum=digest(job)
        if ident in result and result[ident]!=checksum:raise ValueError('Conflicting job snapshots')
        result[ident]=checksum
    return result


def source_families(jobs,aliases=()):
    """Transitive union of confirmed provenance, including absent parent nodes."""
    parent={}
    def find(key):
        parent.setdefault(key,key)
        if parent[key]!=key:parent[key]=find(parent[key])
        return parent[key]
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    fingerprints={}
    for job in jobs:
        ident=job['id'];find(ident)
        for key in ('source_parent_job','parent_job_id','parent_job','source_group_id'):
            if isinstance(job.get(key),str) and job[key]:union(ident,job[key])
        checksum=job.get('source_fingerprint')
        if isinstance(checksum,str) and len(checksum)==64 and all(c in '0123456789abcdef' for c in checksum):
            if checksum in fingerprints:union(ident,fingerprints[checksum])
            fingerprints[checksum]=ident
    for pair in aliases:
        if not isinstance(pair,(list,tuple)) or len(pair)!=2 or not all(isinstance(v,str) and v for v in pair):
            raise ValueError('Confirmed alias requires two source IDs')
        union(*pair)
    members={}
    for ident in list(parent):members.setdefault(find(ident),[]).append(ident)
    groups={root:'source:'+digest({'members':sorted(items)}) for root,items in members.items()}
    return {ident:groups[find(ident)] for ident in parent}


def _events(job,cutoff):
    unique={}
    for raw in job.get('feedback_events',[]):
        event=validate_feedback_event(raw)
        if event['job_id']!=job['id']:raise ValueError('Feedback job mismatch')
        if utc(event['created_at'])>cutoff:continue
        key=event['request_id']
        if key in unique and unique[key]!=event:raise ValueError('Conflicting duplicate human request')
        unique[key]=event
    return sorted(unique.values(),key=lambda e:(e['editorial_revision'],e['created_at'],e['event_id']))


def build_dataset(jobs: list[dict],config: dict,output_dir: Path | None) -> dict:
    """Dry-run by default; write a new immutable directory only when explicitly set."""
    jobs=copy.deepcopy(jobs)
    hashes=input_hashes(jobs);jobs=list({job['id']:job for job in jobs}.values())
    cutoff=utc(config['cutoff']);families=source_families(jobs,config.get('confirmed_aliases',[]))
    holdouts={families[ident] for ident in config.get('holdout_job_ids',[]) if ident in families}
    if set(config.get('holdout_job_ids',[]))-set(families):raise ValueError('Unknown holdout source')
    records=[];event_count=0;legacy_counts={'APPROVED':0,'REJECTED':0};admin_ids=set(config.get('administrative_job_ids',[]))
    for job in sorted(jobs,key=lambda j:j['id']):
        events=_events(job,cutoff);event_count+=len(events)
        group=families[job['id']]
        split='test' if group in holdouts else 'train'
        if not holdouts:
            split='test' if int(hashlib.sha256((str(config.get('seed',17))+group).encode()).hexdigest(),16)%5==0 else 'train'
        for rank,clip in enumerate(job.get('candidates',[])):
            cid=clip.get('candidate_id') or candidate_key(job['id'],rank)
            current=[e for e in events if e['candidate_id']==cid and e['artifact_id']==clip.get('artifact_id') and
                     e['candidate_version']==clip.get('candidate_version') and e['render_revision']==clip.get('render_revision')]
            event=current[-1] if current else None
            admin=job['id'] in admin_ids or bool(event and event['rejection_domain']=='ADMINISTRATIVE')
            authorized=bool(job.get('creator') and job.get('license_note'))
            confirmed=bool(event and authorized and not admin and job.get('editorial_protocol')==2)
            legacy=project_legacy_review(job,rank) if job.get('editorial_protocol',1)!=2 else None
            if legacy and not admin and legacy['legacy_decision'] in legacy_counts:legacy_counts[legacy['legacy_decision']]+=1
            blocking=bool(event and any(e['status']=='OPEN' and e.get('severity') in ('MAJOR','CRITICAL') for e in event['edit_requests']))
            ready=(int(event['decision']=='APPROVED' and clip.get('state') in ('VALID','WARNING') and not blocking) if confirmed else None)
            context=clip.get('editorial_context') or {'text':clip.get('text',''),'source_range':{'start':clip['start'],'end':clip['end']}}
            features=extract_features(context,clip.get('timeline') or {},{}, {'snapshot_id':clip.get('editorial_versions',{}).get('component_snapshot_id','UNKNOWN')})
            records.append({'job_id':job['id'],'source_group_id':group,'candidate_id':cid,
                'candidate_version':clip.get('candidate_version'),'render_revision':clip.get('render_revision'),
                'parent_candidate_version':clip.get('parent_candidate_version'),'artifact_id':clip.get('artifact_id'),
                'comparison_set_id':job['id'],'rank':rank,'score':-rank,'language':job.get('language','UNKNOWN'),'source_fingerprint':job.get('source_fingerprint'),
                'split':split,'human_confirmed':confirmed,'decision':event['decision'] if confirmed else None,
                'content_grade':event['content_grade'] if confirmed else None,'release_ready':ready,
                'technical_state':clip.get('state','UNKNOWN'),'administrative':admin,'authorized':authorized,
                'qualification_status':'CONFIRMED_V2' if confirmed else 'ADMINISTRATIVE' if admin else 'UNKNOWN',
                'legacy_decision':legacy['legacy_decision'] if legacy else None,
                'legacy_comment_raw':legacy['comment_raw'] if legacy and authorized else '',
                'text':context.get('text','') if authorized else '',
                'comment_raw':event['comment_raw'] if confirmed else '',
                'reasons':event['reasons'] if confirmed else [],'dimensions':event['dimensions'] if confirmed else {},'edit_requests':event['edit_requests'] if confirmed else [],
                'relative_assessment':event['relative_assessment'] if confirmed else None,
                'review_timing':event['review_timing'] if confirmed else None,
                'versions':event['versions'] if confirmed else {},'event_id':event['event_id'] if confirmed else None,
                'features':features})
    records.sort(key=lambda r:(r['job_id'],r['rank'],r['candidate_id']))
    criteria={key:config.get(key,default) for key,default in [('cutoff',None),('seed',17),('confirmed_aliases',[]),('holdout_job_ids',[]),('administrative_job_ids',[]),('parent_dataset',None),('raw_input_sha256',{})]}
    manifest={'schema_version':'editorial-dataset-v1','cutoff':config['cutoff'],'criteria':criteria,'input_sha256':hashes,
              'records_sha256':digest(records),'source_groups':len({families[j['id']] for j in jobs}),
              'source_membership':{digest({'node_id':ident}):group for ident,group in sorted(families.items())},
              'candidate_count':len(records),'nonadministrative_candidate_count':sum(not r['administrative'] for r in records),
              'nonadministrative_source_groups':len({r['source_group_id'] for r in records if not r['administrative']}),'human_events_before_cutoff':event_count,
              'eligible_content_candidates':sum(r['content_grade'] is not None for r in records),
              'confirmed_candidates':sum(r['human_confirmed'] for r in records),'legacy_counts':legacy_counts,
              'administrative_jobs':len(admin_ids & set(hashes)),
              'split_groups':{split:sorted({r['source_group_id'] for r in records if r['split']==split}) for split in ('train','test')},
              'feature_schema':'editorial-features-v1','synthetic':config.get('synthetic',False)}
    manifest['dataset_id']=digest(manifest)
    result={'manifest':manifest,'records':records}
    reader=config.get('snapshot_reader')
    if reader and reader()!=hashes:raise ValueError('Input snapshot changed during export')
    if not config.get('dry_run',True):
        if output_dir is None or not config.get('export_root'):raise ValueError('Explicit export root and destination required')
        root=Path(config['export_root']).resolve();target=Path(output_dir).resolve()
        if target==root or not target.is_relative_to(root):raise ValueError('Unsafe export path')
        if target.exists():raise FileExistsError('Dataset destination is immutable')
        root.mkdir(parents=True,exist_ok=True)
        if not target.parent.is_dir():raise ValueError('Export parent must already exist')
        stage=target.parent/('.editorial-export-'+uuid.uuid4().hex);stage.mkdir()
        try:
            for name,value in result.items():
                (stage/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
            if reader and reader()!=hashes:raise ValueError('Input snapshot changed before publication')
            from .store import file_lock
            with file_lock(root/'.export.lock'):
                if target.exists():raise FileExistsError('Dataset destination is immutable')
                os.rename(stage,target)
        finally:
            if stage.exists():
                for name in ('manifest.json','records.json'):(stage/name).unlink(missing_ok=True)
                stage.rmdir()
    return result


def evaluate_pool(records: list[dict],config: dict) -> dict:
    """Linear gain, averaged score ties, fixed three slots; unknown stays unknown."""
    pools={};seen={};administrative_queries=set()
    for row in records:
        if row.get('administrative'):
            administrative_queries.add(row.get('comparison_set_id',row['source_group_id']))
            continue
        key=(row['candidate_id'],row.get('artifact_id'),row.get('comparison_set_id',row['source_group_id']))
        if key in seen:
            if seen[key]!=row:raise ValueError('Conflicting evaluation duplicate')
            continue
        seen[key]=row;pools.setdefault(key[2],[]).append(row)
    clean=[];adjusted=[];precision=[];ndcg=[];zero=0;reason_counts={};reason_covered=0;reviewed=0;active=[];wall=[];edits={}
    for pool in pools.values():
        for row in pool:
            score=row.get('score',-row.get('rank',0))
            if type(score) not in (float,int) or not math.isfinite(score):raise ValueError('Invalid evaluation score')
            grade=row.get('content_grade')
            if grade is not None and (type(grade) is not int or not 0<=grade<=3):raise ValueError('Invalid evaluation grade')
        pool=sorted(pool,key=lambda r:-r.get('score',-r.get('rank',0)));top=pool[:3]
        if all(r.get('human_confirmed') and r.get('decision') in ('APPROVED','APPROVED_WITH_ADJUSTMENTS','REJECTED') for r in top):
            clean.append(sum(r['decision']=='APPROVED' for r in top)/3)
            adjusted.append(sum(r['decision']=='APPROVED_WITH_ADJUSTMENTS' for r in top)/3)
        if all(r.get('human_confirmed') and r.get('content_grade') is not None for r in top):
            precision.append(sum(r['content_grade']>=2 for r in top)/3)
        if all(r.get('human_confirmed') and r.get('content_grade') is not None for r in pool):
            ideal=sum(g/math.log2(i+2) for i,g in enumerate(sorted((r['content_grade'] for r in pool),reverse=True)[:3]))
            if ideal:
                dcg=0;offset=0
                while offset<len(pool):
                    end=offset+1;score=pool[offset].get('score',-pool[offset].get('rank',0))
                    while end<len(pool) and pool[end].get('score',-pool[end].get('rank',0))==score:end+=1
                    avg=sum(r['content_grade'] for r in pool[offset:end])/(end-offset)
                    dcg+=avg*sum(1/math.log2(i+2) for i in range(offset,min(end,3)));offset=end
                ndcg.append(dcg/ideal)
            else:zero+=1
        for row in pool:
            if not row.get('human_confirmed'):continue
            reviewed+=1;codes={r['code'] for r in row.get('reasons',[]) if r.get('confirmed_by')=='human'}
            reason_covered+=bool(codes)
            if row.get('decision')=='REJECTED':
                for code in codes:reason_counts[code]=reason_counts.get(code,0)+1
            timing=row.get('review_timing') or {}
            if timing.get('active_seconds') is not None:active.append(timing['active_seconds'])
            if timing.get('wall_seconds') is not None:wall.append(timing['wall_seconds'])
            for edit in row.get('edit_requests',[]):edits[(row['source_group_id'],edit['edit_id'])]=edit['status']
    dimensions={}
    codes_by_dimension={'closure':{'INCOMPLETE_PAYOFF','ABRUPT_ENDING','MISSING_DEMONSTRATION'},
                        'framing':{'BAD_FRAMING','IMPORTANT_CONTENT_CROPPED'}}
    for dimension,codes in codes_by_dimension.items():
        evaluated=problems=0
        for row in seen.values():
            if not row.get('human_confirmed'):continue
            found=bool(codes & {r['code'] for r in row.get('reasons',[]) if r.get('confirmed_by')=='human'})
            evaluated+=found or row.get('dimensions',{}).get(dimension) is not None
            problems+=found
        dimensions[dimension]={'evaluated':evaluated,'problem_count':problems,
            'rate_where_evaluated':problems/evaluated if evaluated else None,
            'rate_all_reviewed':problems/reviewed if reviewed else None,
            'coverage':evaluated/reviewed if reviewed else 0}
    comparisons={};unverifiable=set()
    for pool in pools.values():
        current={r['candidate_id']:r for r in pool}
        for row in pool:
            relative=row.get('relative_assessment')
            if not row.get('human_confirmed') or not relative or relative.get('confirmed_by')!='human':continue
            ident=relative['comparison_set_id']
            if not all(a['candidate_id'] in current and all(
                    current[a['candidate_id']].get(key) is not None and a.get(key)==current[a['candidate_id']][key]
                    for key in ('candidate_version','render_revision','artifact_id')) for a in relative['alternatives']):
                unverifiable.add(ident)
                continue
            if ident in comparisons and comparisons[ident]!=relative:raise ValueError('Conflicting relative comparison')
            comparisons[ident]=relative
    comparisons={ident:value for ident,value in comparisons.items() if ident not in unverifiable}
    winners={}
    for relative in comparisons.values():
        winner=relative['preferred_candidate_id'];winners[winner]=winners.get(winner,0)+1
    relative_report={'confirmed_sets':len(comparisons),'winners_by_candidate':winners,
                     'excluded_stale_or_unverifiable_sets':len(unverifiable),
                     'all_options_below_bar':sum(r['all_options_below_bar'] for r in comparisons.values()),
                     'ties':'NOT_RECORDED_BY_V2_CONTRACT'}
    mean=lambda xs:sum(xs)/len(xs) if xs else None
    return {'queries_generated':len(pools),'excluded_administrative_queries':len(administrative_queries),
            'decision_queries_eligible':len(clean),'grade_queries_eligible':len(precision),
            'decision_query_coverage':len(clean)/len(pools) if pools else 0,'grade_query_coverage':len(precision)/len(pools) if pools else 0,
            'acceptance_at_3_clean':mean(clean),'acceptance_at_3_adjusted':mean(adjusted),
            'approved_per_video_clean':3*mean(clean) if clean else None,'precision_at_3':mean(precision),'ndcg_at_3':mean(ndcg),
            'ndcg_queries_eligible':len(ndcg),'excluded_zero_idcg':zero,'rejection_reason_counts':reason_counts,
            'reasons_coverage':reason_covered/reviewed if reviewed else 0,'reviewed_candidates':reviewed,
            'mean_active_review_seconds':mean(active),'mean_wall_review_seconds':mean(wall),
            'edit_requests_distinct':len(edits),'edits_resolved':sum(status=='RESOLVED' for status in edits.values()),
            'problem_dimensions':dimensions,'relative_preferences':relative_report,
            'inference':'DESCRIPTIVE_ONLY','config_sha256':digest(config)}
