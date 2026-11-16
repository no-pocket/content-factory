"""Explicit private-browser DTOs. Never return persistence records wholesale."""
from __future__ import annotations

import re
import copy
import threading
from pathlib import Path
from collections import defaultdict, OrderedDict
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import service
from .artifacts import artifact_manifest, digest
from .editorial_contracts import DIMENSIONS
from .timeline import candidate_duration
from .editorial_rework import enabled as auto_rework_enabled


def diagnostic(value):
    """Remove backend paths/addresses from nested diagnostic data, retaining QC facts."""
    if isinstance(value, dict):
        return {k: diagnostic(v) for k, v in value.items()
                if not any(word in k.lower() for word in ('token', 'secret', 'credential', 'path', 'file', 'url', 'endpoint'))}
    if isinstance(value, list):
        return [diagnostic(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'\b(?:https?|redis)://\S+', '[serviço local]', value)
        value = re.sub(r'[A-Za-z]:[\\/][^\s,;]+|/(?:data|app|workspace|srv|run|tmp|Users)(?:/[^\s,;]*)?', '[arquivo local]', value)
        return value[:8000]
    return value


_views = OrderedDict()
_views_lock = threading.Lock()


def job_view(job):
    # Polling must not reread every master on the Windows bind mount. Any JSON or
    # file identity/size/mtime/ctime change invalidates this presentation cache.
    # The review service still hashes bytes freshly under its mutation lock.
    stats = []
    for c in job.get('candidates', []):
        master = Path(c['file']) if c.get('file') else None
        for path in (master, master.with_suffix('.preview.webm') if master else None,
                     Path(c['timeline_file']) if c.get('timeline_file') else master.with_suffix('.timeline.json') if master else None):
            try:
                s = path.stat() if path else None
                stats.append((str(path), s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) if s else None)
            except OSError:
                stats.append(None)
    signature = (digest(job), tuple(stats))
    with _views_lock:
        cached = _views.get(job['id'])
        if cached and cached[0] == signature:
            return copy.deepcopy(cached[1])
    result = _job_view(job)
    with _views_lock:
        _views[job['id']] = (signature, result)
        _views.move_to_end(job['id'])
        if len(_views) > 128:
            _views.popitem(last=False)
    return copy.deepcopy(result)


def _job_view(job):
    editorial = service.get_editorial_view(job)
    cands = []
    protocol = job.get('editorial_protocol', 1)
    for i, row in enumerate(editorial['candidates']):
        clip = job['candidates'][i]
        if protocol == 2:
            history = [{'at': datetime.fromisoformat(e['created_at'].replace('Z', '+00:00')).timestamp() * 1000,
                        'dec': e['decision'], 'comment': e['comment_raw'], 'by': e['actor']['channel']}
                       for e in row['history']]
            artifact = row['artifact_id']
            revision = editorial['editorial_revision']
        else:
            history = [{'at': e['at'] * 1000, 'dec': d['decision'], 'comment': d.get('reason', ''), 'by': e.get('origin', 'legado')}
                       for e in job.get('decision_history', []) for d in e.get('decisions', []) if d['candidate'] == i]
            artifact = 'sha256:' + digest(artifact_manifest(job, i, presentation_cache=True))
            revision = len(job.get('decision_history', []))
        cands.append({'id': row['candidate_id'], 's': clip.get('start', 0), 'e': clip.get('end', 0),
                      'title': clip.get('title') or next((t.get('text') for t in (clip.get('timeline') or {}).get('layers', {}).get('text', []) if t.get('text')), ''),
                      'heu': clip.get('score'), 'w': clip.get('word_count'), 'qc': row['technical_state'],
                      'ai': clip.get('ai_reason') or clip.get('reason', ''), 'tx': clip.get('text', ''),
                      'artifact': artifact, 'intact': row['artifact_intact'] if protocol == 2 else True,
                      'revision': revision, 'candidate_version': row['candidate_version'], 'render_revision': row['render_revision'],
                      'model': (job.get('comparison') or {}).get('label') or (job.get('settings') or {}).get('llm_model') or job.get('ranker_used', 'Legado'),
                      'dec': row['normalized_decision'] or 'UNCONFIRMED_LEGACY', 'hist': history,
                      'rating': row.get('dimensions', {}), 'grade': row.get('content_grade'),
                      'edits': row.get('edit_requests', []), 'director': clip.get('director_used', 'legado'),
                      'renderer': clip.get('renderer_used', 'legado'), 'attempts': clip.get('attempts', 0),
                      'diagnostic': diagnostic(clip.get('qc')), 'story': diagnostic(clip.get('story_assessment')),
                      'boundary_review_required': bool(clip.get('boundary_review_required')),
                      'boundary_confirmed': service.audio_boundary_confirmed(clip),
                      'assembly': diagnostic(clip.get('assembly')), 'pace': diagnostic(clip.get('pace')),
                      'word_timing':diagnostic((clip.get('timeline') or {}).get('word_timing_diagnostics')),
                      'title_diagnostic':diagnostic((clip.get('timeline') or {}).get('editorial_title_diagnostics')),
                      'output_seconds':candidate_duration(clip), 'captions': diagnostic(clip.get('social_captions'))})
    settings = job.get('settings') or {}
    request = job.get('editorial_request') or {}
    plan = request.get('plan') or {}
    expires = request.get('expires_at')
    return {'id': job['id'], 'name': job.get('video_title') or (job.get('youtube_metadata') or {}).get('title') or job['original_name'], 'who': job['creator'], 'lic': job['license_note'],
            'video_id': job.get('youtube_video_id') or (job.get('youtube_metadata') or {}).get('video_id'),
            'st': job['status'], 'lang': job.get('language', ''), 'eng': job.get('ranker_used') or settings.get('llm_backend', 'legado'),
            'dur': job.get('duration'), 'created': job.get('created_at', 0) * 1000, 'cands': cands,
            'settings': settings, 'qc_settings': job.get('qc_settings', {}), 'protocol': protocol,
            'parent_id':job.get('source_parent_job') if job.get('editorial_rework') else None,
            'auto_rework_enabled':auto_rework_enabled(),
            'reworks':[{k:r.get(k) for k in ('child_id','state','error','review_revision')} for r in job.get('rework_requests',[])],
            'review_status': editorial['review_status'], 'error': diagnostic(job.get('error')),
            'editorial_result': diagnostic({'reason': plan.get('reason'),
                                           'run_id': (job.get('processing_runs') or [{}])[-1].get('run_id'),
                                           'failure_code': request.get('failure_code'), 'state':request.get('state'),
                                           'deadline_ms':expires*1000 if type(expires) in (int,float) else None,
                                           'requested_planner':settings.get('editorial_planner'),
                                           'effective_planner':job.get('ranker_used'),
                                           'planner':plan.get('planner'), 'transcription':job.get('transcript_model'),
                                           'fallback': job.get('editorial_planner_fallback')}),
            'events': diagnostic(job.get('ai_events', [])), 'activity': diagnostic(job.get('ai_activity'))}


def source_view(r):
    return {'id': r['channel_id'], 'name': r['name'], 'status': r['status'], 'ref': r['authorization_reference'],
            'rights': r['rights_confirmed'], 'platform': r['platform_permission'], 'langs': ','.join(r['allowed_languages']),
            'kinds': r['allowed_video_kinds'], 'scopes': r['allowed_model_scopes'], 'rev': r['revision']}


def item_view(r):
    d = r['draft']
    link = r.get('permalink')
    parsed = urlsplit(link) if isinstance(link, str) else None
    public_link = link if parsed and parsed.scheme == 'https' and parsed.netloc in ('www.instagram.com', 'instagram.com', 'www.facebook.com', 'facebook.com') else None
    return {'id': r['id'], 'at': r['scheduled_at'] * 1000, 'pv': d['provider'], 'st': r['state'], 't': d['title'],
            'job_id': d['job_id'], 'candidate_id': d['candidate_id'], 'artifact': d['artifact_id'],
            'caption': d.get('description', ''), 'timezone': r.get('timezone', 'America/Sao_Paulo'),
            'error': diagnostic(r.get('error')), 'remote_id': r.get('remote_id'), 'remote_container_id': r.get('remote_container_id'), 'failure_stage': r.get('failure_stage'), 'failure_kind': r.get('failure_kind'), 'permalink': public_link}


def metrics_view(jobs):
    """Human metrics; unknown/legacy grades remain distinct from zero."""
    from .editorial_dataset import build_dataset
    from .editorial_models import summarize_training_records, GATES
    from .editorial import summarize, summarize_v2
    models = defaultdict(lambda: {'reviewed': 0, 'approved': 0, 'adjusted': 0, 'rejected': 0, 'pending': 0})
    dims = {k: [] for k in DIMENSIONS}
    grades = {str(n): 0 for n in range(4)}
    grades['unknown'] = 0
    for job in jobs:
        for c in job_view(job)['cands']:
            m = models[c['model']]
            d = c['dec']
            m['pending'] += d in ('PENDING', 'UNCONFIRMED_LEGACY')
            if d in ('APPROVED', 'APPROVED_WITH_ADJUSTMENTS', 'REJECTED'):
                m['reviewed'] += 1
                m[{'APPROVED': 'approved', 'APPROVED_WITH_ADJUSTMENTS': 'adjusted', 'REJECTED': 'rejected'}[d]] += 1
            grades['unknown' if c['grade'] is None else str(c['grade'])] += 1
            for key, value in c['rating'].items():
                if key in dims and value is not None:
                    dims[key].append(value)
    dataset = build_dataset(jobs, {'cutoff': datetime.now(timezone.utc).isoformat(), 'dry_run': True}, None)
    readiness = summarize_training_records(dataset['records'])
    return {'models': dict(models), 'dimensions': {k: {'mean': round(sum(v) / len(v), 2) if v else None, 'n': len(v)} for k, v in dims.items()},
            'grades': grades, 'readiness': readiness, 'gates': GATES, 'automatic_training': False,
            'configuration_comparison': diagnostic(summarize(jobs)), 'source_comparison': diagnostic(summarize_v2(jobs))}
