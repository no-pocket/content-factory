"""Content-free stage timings tied to a job, configuration and render revision."""
from contextlib import contextmanager
import time
import uuid


def job_metric_context(job: dict, index: int | None=None, render_revision: int | None=None) -> dict:
    from .artifacts import digest
    from .editorial_contracts import candidate_key
    context={'job_id':job['id'],'configuration_sha256':digest({'settings':job.get('settings'),
             'qc_settings':job.get('qc_settings'),'pipeline_version':job.get('pipeline_version','UNKNOWN')}),
             'component_snapshot_id':job.get('processing_snapshot',job.get('component_snapshot',{})).get('snapshot_id','UNKNOWN'),
             'processing_run_id':job.get('processing_runs',[{}])[-1].get('run_id','UNKNOWN') if job.get('processing_runs') else 'UNKNOWN'}
    if job.get('processing_runs'):
        context['component_snapshot_id']=job['processing_runs'][-1].get('component_snapshot',{}).get('snapshot_id',context['component_snapshot_id'])
    if index is not None:
        clip=job['candidates'][index]
        try:cid=clip.get('candidate_id') or candidate_key(job['id'],index)
        except ValueError:cid='UNKNOWN'
        context.update(candidate_id=cid,candidate_version=clip.get('candidate_version',1),render_revision=render_revision)
    return context


@contextmanager
def measure_stage(metrics: list, stage: str, context: dict | None=None, **details):
    allowed={'job_id','candidate_id','candidate_version','render_revision','configuration_sha256',
             'component_snapshot_id','processing_run_id','image_id'}
    if context and set(context)-allowed:raise ValueError('Unsupported metric context fields')
    metric={'schema_version':'1.0','metric_id':str(uuid.uuid4()),'stage':stage,'state':'RUNNING',
            'started_at':time.time(),'seconds':None,**(context or {}),**details}
    started=time.perf_counter()
    try:
        yield metric
        if metric['state']=='RUNNING':metric['state']='COMPLETED'
    except BaseException as exc:
        metric.update(state='FAILED',error_type=type(exc).__name__)
        raise
    finally:
        metric['seconds']=round(time.perf_counter()-started,6)
        metric['finished_at']=time.time()
        metrics.append(metric)
