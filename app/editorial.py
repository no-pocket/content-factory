"""Evaluation signals stay independent of ranking. No automatic learning."""
from __future__ import annotations

import hashlib
import json
from itertools import combinations

DIMENSIONS = ('hook', 'context', 'closure', 'captions')


def current_decisions(job: dict) -> dict:
    history=job.get('decision_history', [])
    if not history:
        return {}
    event=history[-1]
    invalid=job.get('candidate_review_invalidated_at')
    return {d['candidate']: d for d in event['decisions']
            if event['at'] > (invalid.get(str(d['candidate']),0) if invalid is not None
                              else job.get('review_invalidated_at',0))}


def config_id(job: dict) -> str:
    payload = {'settings': job.get('settings'), 'qc': job.get('qc_settings'),
               'version': job.get('pipeline_version', 'legacy')}
    if job.get('evaluation', {}).get('variant'):
        payload['evaluation_variant'] = job['evaluation']['variant']
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def validate_decision(value: dict, count: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError('Decision must be object')
    if type(value.get('candidate')) is not int or not 0 <= value['candidate'] < count:
        raise ValueError('Invalid candidate index')
    if value.get('decision') not in {'APPROVED', 'REJECTED'}:
        raise ValueError('Invalid editorial decision')
    for key in DIMENSIONS:
        if value.get(key) is not None and (type(value[key]) is not int or not 1 <= value[key] <= 5):
            raise ValueError(f'{key} must be 1..5')
    for key in ('reason', 'adjustments'):
        if not isinstance(value.get(key), str) or len(value[key]) > 4000:
            raise ValueError(f'{key} must be text, max 4000')
    if not value['reason'].strip() or type(value.get('rework')) is not bool:
        raise ValueError('Reason and rework flag required')
    if value['rework'] and not value['adjustments'].strip():
        raise ValueError('Describe required adjustments')
    return {key: value.get(key) for key in ('candidate', 'decision', 'reason', *DIMENSIONS, 'rework', 'adjustments')}


def summarize(jobs: list[dict]) -> dict:
    # One latest reviewed run per source/configuration; never count repeated runs as new videos.
    groups = {}
    unreviewed = 0
    for job in jobs:
        history = job.get('decision_history', [])
        if not history or history[-1]['at'] <= job.get('review_invalidated_at', 0) or not history[-1].get('review_complete', True):
            unreviewed += 1
            continue
        source = job.get('source_fingerprint') or job.get('source_url') or job.get('source') or job['id']
        key = (source, config_id(job))
        if key not in groups or history[-1]['at'] > groups[key]['decision_history'][-1]['at']:
            groups[key] = job
    def aggregate(values):
        decisions = [d for j in values for d in j['decision_history'][-1]['decisions']]
        approved = sum(d['decision'] == 'APPROVED' for d in decisions)
        elapsed = [sum(r.get('seconds', max(0, r.get('last_checkpoint_at', r.get('started_at', 0)) - r.get('started_at', 0)))
                       for r in j.get('processing_runs', [])) for j in values if j.get('processing_runs')]
        return {'reviewed_videos': len(values), 'reviewed_candidates': len(decisions), 'approved_candidates': approved,
                'approved_per_video': approved / len(values) if values else None,
                'rework_rate': sum(d['rework'] for d in decisions) / len(decisions) if decisions else None,
                'processing_mean_seconds': sum(elapsed) / len(elapsed) if elapsed else None,
                'processing_measured_videos': len(elapsed)}
    configs = {}
    for (_, configuration), job in groups.items():
        configs.setdefault(configuration, []).append(job)
    # Across configurations use one latest reviewed run per source. Comparisons belong to cohorts.
    latest = {}
    for (source, _), job in groups.items():
        if source not in latest or job['decision_history'][-1]['at'] > latest[source]['decision_history'][-1]['at']:
            latest[source] = job
    result = aggregate(list(latest.values()))
    result['video_configuration_pairs'] = len(groups)
    result['interrupted_timing_jobs'] = sum(any(not r.get('timing_complete', True) for r in j.get('processing_runs', []))
                                            for j in latest.values())
    result.update(unreviewed_jobs=unreviewed, by_configuration={c: aggregate(v) for c, v in configs.items()},
                  conclusion='Descriptive only; requires paired videos and human review before changing selection')
    paired = []
    for a, b in combinations(sorted(configs), 2):
        common = sorted(source for source, configuration in groups if configuration == a and (source, b) in groups)
        rows = []
        for source in common:
            left, right = groups[(source, a)], groups[(source, b)]
            lm, rm = aggregate([left]), aggregate([right])
            rows.append({'source': source, 'baseline_job': left['id'], 'variant_job': right['id'],
                         'approval_delta': rm['approved_candidates'] - lm['approved_candidates'],
                         'rework_delta': rm['rework_rate'] - lm['rework_rate']
                         if rm['rework_rate'] is not None and lm['rework_rate'] is not None else None})
        paired.append({'configuration_a': a, 'configuration_b': b, 'paired_videos': len(rows),
                       'approval_delta_per_video': sum(r['approval_delta'] for r in rows) / len(rows) if rows else None,
                       'rows': rows, 'note': 'B minus A; configuration labels are hashes, not quality ordering'})
    decisions = [d for j in latest.values() for d in j['decision_history'][-1]['decisions']]
    rated = {key: [d[key] for d in decisions if d.get(key) is not None] for key in DIMENSIONS}
    averages = {key: sum(values) / len(values) if values else None for key, values in rated.items()}
    languages = {}
    for job in latest.values():
        languages.setdefault(job.get('language', 'unknown'), []).append(job)
    result.update(paired_comparisons=paired,
                  by_language={language: aggregate(values) for language, values in languages.items()},
                  technical_failed_candidates=sum(c.get('state') == 'FAILED' for j in jobs for c in j.get('candidates', [])),
                  legacy_approved_jobs=sum(bool(j.get('approved')) and not j.get('decision_history') for j in jobs),
                  refinement={'dimension_means': averages, 'reviewed_sources': len(latest),
                              'sufficient_for_general_rule': False, 'automatic_selection_update': False,
                              'next_step': 'Review the authorized pilot corpus by language; inspect low dimensions, reasons and paired results before proposing a rule. Expand the corpus before generalizing.'})
    return result


def summarize_v2(jobs: list[dict]) -> dict:
    """Descriptive, source-grouped top-three yield with unknown coverage explicit."""
    from .service import get_editorial_view
    groups = {}
    for job in jobs:
        source = job.get('source_group_id') or job.get('source_fingerprint') or job.get('source_url') or job['id']
        key = (source, job.get('comparison_set_id') or config_id(job))
        if key not in groups or job.get('created_at', 0) > groups[key].get('created_at', 0):
            groups[key] = job
    views = [get_editorial_view(job) for job in groups.values()]
    rows = [row for view in views for row in view['candidates']]
    eligible = [view['candidates'][:3] for view in views if view['candidates'] and
                all(r['normalized_decision'] in ('APPROVED', 'APPROVED_WITH_ADJUSTMENTS', 'REJECTED')
                    for r in view['candidates'][:3])]
    return {'queries_total': len(views), 'queries_eligible': len(eligible),
            'review_coverage': len(eligible)/len(views) if views else None,
            'clean_approved': sum(r['normalized_decision'] == 'APPROVED' for r in rows),
            'approved_with_adjustments': sum(r['normalized_decision'] == 'APPROVED_WITH_ADJUSTMENTS' for r in rows),
            'rejected': sum(r['normalized_decision'] == 'REJECTED' for r in rows),
            'pending': sum(r['normalized_decision'] == 'PENDING' for r in rows),
            'unconfirmed_legacy': sum(r['qualification_status'] == 'UNCONFIRMED_LEGACY' for r in rows),
            'acceptance_at_3_clean': sum(sum(r['normalized_decision'] == 'APPROVED' for r in pool)/3 for pool in eligible)/len(eligible) if eligible else None,
            'acceptance_at_3_adjustments': sum(sum(r['normalized_decision'] == 'APPROVED_WITH_ADJUSTMENTS' for r in pool)/3 for pool in eligible)/len(eligible) if eligible else None,
            'note': 'Descriptive only; unknown reviews excluded, missing top-three slots contribute zero.'}
