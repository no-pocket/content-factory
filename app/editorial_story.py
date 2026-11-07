"""Conservative story diagnostics. Automatic signals are never human ratings."""
from __future__ import annotations

import copy
import math
import re
import unicodedata


def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


PROMOTION = re.compile(r'\b(minha live|meu canal|inscreva|deixe o like|se inscrev|subscribe|my stream|my channel|hit the like)')
DANGLING = re.compile(r'(vou mostrar|vamos mostrar|vamos ver|let me show(?: you)?|i.ll show(?: you)?|ele e|ela e|it is|this is|tipo[\s,]+sei la|porque|because|e ai|and then)[\s.!?,:;]*$')
PAYOFF = re.compile(r'\b(aqui esta|aqui vemos|mostra|demonstra|revela|conclu|portanto|here is|here we see|shows|demonstrat|reveals|therefore)')


def _all_segments(context):
    return context.get('before', []) + context.get('segments', []) + context.get('after', [])


def validate_story_boundary(plan: dict, context: dict) -> dict:
    if set(plan) != {'source_start', 'source_end'}:
        raise ValueError('Invalid story boundary fields')
    start, end = plan['source_start'], plan['source_end']
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end)) or not 0 <= start < end:
        raise ValueError('Invalid story boundary')
    segments = _all_segments(context)
    if not segments or start < min(s['source_start'] for s in segments) or end > max(s['source_end'] for s in segments):
        raise ValueError('Boundary outside observed source context')
    for segment in segments:
        for word in segment.get('words', []):
            if word['source_start'] < end and word['source_end'] > start:
                if word['source_start'] < start-1e-6 or word['source_end'] > end+1e-6:
                    raise ValueError('Story boundary cuts a source word')
    return {'valid': True, 'source_start': start, 'source_end': end, 'word_timing_available': any(s.get('words') for s in segments)}


def assess_story(context: dict, policy: dict, model_result: dict | None) -> dict:
    text = context.get('text', '')
    folded = _fold(text)
    sentences = [s for s in re.split(r'[.!?\n]+', folded) if s.strip()]
    promotions = sum(bool(PROMOTION.search(s)) for s in sentences)
    dominant = bool(sentences) and promotions > len(sentences)/2
    incomplete = bool(DANGLING.search(folded))
    segments = _all_segments(context)
    result = {'schema_version': '1.0', 'rule_version': 'story-v1',
              'relevance': 'SELF_PROMOTION_DOMINANT' if dominant else 'UNCERTAIN',
              'closure': 'INCOMPLETE' if incomplete else 'UNCERTAIN',
              'quality_uncertain': True, 'content_grade': None, 'human_ratings': None,
              'fallback_reason': 'no_valid_semantic_model_assessment', 'evidence': [],
              'proposed_source_end': None, 'last_thought': text.splitlines()[-1] if text else '',
              'parts': {'hook': None, 'setup': None, 'proof': None, 'payoff': None}}
    if model_result is not None:
        try:
            if not isinstance(model_result, dict) or set(model_result)-{'closure', 'evidence', 'parts'} or model_result.get('closure') not in ('COMPLETE', 'INCOMPLETE', 'UNCERTAIN'):
                raise ValueError('Invalid story shape')
            evidence = model_result.get('evidence')
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 12:
                raise ValueError('Missing story evidence')
            anchored = []
            for item in evidence:
                if not isinstance(item, dict) or set(item) != {'segment_id', 'quote'} or type(item['segment_id']) is not int or not isinstance(item['quote'], str) or not item['quote'].strip():
                    raise ValueError('Invalid evidence')
                source = next((s for s in segments if s['segment_id'] == item['segment_id']), None)
                if source is None or item['quote'] not in source['text'] or len(item['quote']) > 1000:
                    raise ValueError('Evidence not in source')
                if source['source_start'] < context['source_range']['start'] or source['source_end'] > context['source_range']['end']:
                    raise ValueError('Evidence outside candidate')
                anchored.append({**item, 'source_start': source['source_start'], 'source_end': source['source_end']})
            if model_result['closure'] == 'COMPLETE' and not any(e['source_end'] >= context['source_range']['end']-.05 for e in anchored):
                raise ValueError('Missing ending evidence')
            result.update(closure='INCOMPLETE' if incomplete else model_result['closure'], evidence=anchored,
                          fallback_reason=None, assessment_source='model_with_source_evidence')
            parts = model_result.get('parts', {})
            if not isinstance(parts, dict) or set(parts)-set(result['parts']):
                raise ValueError('Invalid story parts')
            for key, reference in parts.items():
                if reference is not None and (type(reference) is not int or reference not in [e['segment_id'] for e in anchored]):
                    raise ValueError('Part without source evidence')
                result['parts'][key] = reference
        except (ValueError, TypeError, KeyError):
            result.update(fallback_reason='invalid_model_evidence', evidence=[], closure='INCOMPLETE' if incomplete else 'UNCERTAIN')
    if result['closure'] == 'INCOMPLETE':
        start = context['source_range']['start']
        maximum = policy.get('max_seconds', 60)
        for segment in context.get('after', []):
            if segment['source_end'] - start > maximum:
                break
            if PAYOFF.search(_fold(segment['text'])) and not DANGLING.search(_fold(segment['text'])):
                try:
                    boundary = validate_story_boundary({'source_start': start, 'source_end': segment['source_end']}, context)
                except ValueError:
                    continue
                result['proposed_source_end'] = boundary['source_end']
                result['extension_reason'] = 'possible_payoff_in_following_source_segment_requires_review'
                break
    return result


def annotate_candidates(clips: list[dict], segments: list[dict], policy: dict | None = None, *, max_seconds=60) -> list[dict]:
    from .editorial_context import build_candidate_context
    output = copy.deepcopy(clips)
    job = {'candidates': output}
    for index, clip in enumerate(output):
        context = build_candidate_context(job, index, {'segments': segments})
        story = assess_story(context, {'max_seconds': max_seconds}, None)
        if story['proposed_source_end'] is not None:
            clip['baseline_window'] = {'start': clip['start'], 'end': clip['end']}
            clip['end'] = story['proposed_source_end']
            context = build_candidate_context(job, index, {'segments': segments})
            story = assess_story(context, {'max_seconds': max_seconds}, None)
            story['boundary_adjusted'] = True
        clip.update(editorial_context=context, text=context['text'], editorial_policy=policy or {'brief': None},
                    story_assessment=story)
        clip['editorial_penalty'] = (50 if story['relevance'] == 'SELF_PROMOTION_DOMINANT' else 0) + (40 if story['closure'] == 'INCOMPLETE' else 0)
    return sorted(output, key=lambda c: c['editorial_penalty'])
