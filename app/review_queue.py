"""Operational review queue based on decisions for the current candidate renders."""
from __future__ import annotations
from .service import get_editorial_view

DECIDED = {'APPROVED', 'APPROVED_WITH_ADJUSTMENTS', 'REJECTED'}
REVIEWABLE = {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'}


def _reviewed(row):
    return row['normalized_decision'] in DECIDED or (
        row['normalized_decision'] is None and row.get('legacy_decision') in {'APPROVED', 'REJECTED'})


def review_progress(job, view=None):
    rows = (view or get_editorial_view(job))['candidates']
    count = sum(_reviewed(row) for row in rows)
    return {'total': len(rows), 'reviewed': count, 'complete': bool(rows) and count == len(rows)}


def needs_review(job, view=None):
    if job.get('status') not in REVIEWABLE:
        return False
    rows = (view or get_editorial_view(job))['candidates']
    return any(not _reviewed(row) and (job.get('editorial_protocol') == 2 or
               row['technical_state'] in {'VALID', 'WARNING'}) for row in rows)


def completion_identity(job):
    return [(row['candidate_id'], row['candidate_version'], row['render_revision'], row['artifact_id'])
            for row in get_editorial_view(job)['candidates']]


def apply_completion(state, jobs):
    """Apply a fragment's intent before select widgets are instantiated."""
    token = state.pop('review_queue_transition', None)
    if not token:
        return False
    completed = next((job for job in jobs if job['id'] == token['job_id']), None)
    if not completed or not review_progress(completed)['complete'] or completion_identity(completed) != token['identity']:
        return False
    pending = [job for job in reversed(jobs) if needs_review(job)]
    next_id = pending[0]['id'] if pending else None
    state['job_filter'] = 'Para revisar'
    state['candidate_filter'] = None
    if next_id:
        state['selected_job'] = next_id
    else:
        state.pop('selected_job', None)
    total = len(completed['candidates'])
    state['review_queue_confirmation'] = f"Revisão concluída: {total} de {total} candidatos salvos. " + (
        'Próximo job pendente aberto.' if next_id else 'Parabéns! Todos os jobs disponíveis para revisão foram avaliados.')
    return True
