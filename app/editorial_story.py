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


def safe_source_end(context: dict, *, max_seconds: float) -> dict:
    """Find a bounded sentence endpoint, never infer narrative completion from it.

    Whisper segments are transport chunks, not sentences. Prefer word punctuation
    and keep up to 150 ms of observed silence after speech, without adding the
    next word. Missing timing falls back explicitly to segment punctuation.
    """
    start, end = context['source_range']['start'], context['source_range']['end']
    segments = sorted(_all_segments(context), key=lambda s: s['source_start'])
    units = []
    for segment in segments:
        units.extend(segment.get('words') or [segment])
    units.sort(key=lambda u: (u['source_start'], u['source_end']))
    selected = [u for u in units if u['source_start'] < end and u['source_end'] > start]
    if not selected:
        return {'source_end': end, 'reason': 'no_observed_speech_boundary', 'resolved': False}
    last = selected[-1]
    terminal = lambda u: bool(re.search(r'(?<!\.)[.!?]["\'”’)]*$', u['text'].strip())) and not u['text'].strip().endswith('...')
    requires_completion = last['source_end'] > end or not terminal(last)
    endpoint = last if not requires_completion else next((u for u in units
        if u['source_end'] >= last['source_end'] and u['source_end']-start <= max_seconds
        and terminal(u)), None)
    if endpoint is None:
        return {'source_end': end, 'reason': 'no_complete_sentence_within_observed_budget', 'resolved': False}
    from .narrative import inspect
    narrative, extension = inspect(context, max_seconds=max_seconds)
    if narrative['blocking_obligations']:
        if extension is None:
            return {'source_end': end, 'reason': 'unresolved_narrative_obligation', 'resolved': False}
        endpoint = next((u for u in units if u['source_end'] == extension), None)
        if endpoint is None or not terminal(endpoint):
            return {'source_end': end, 'reason': 'no_safe_payoff_boundary', 'resolved': False}
    speech_end = endpoint['source_end']
    observed_end = max(s['source_end'] for s in segments)
    following = [u['source_start'] for u in units if u['source_start'] >= speech_end and u is not endpoint]
    padded = min(speech_end+.15, min(following, default=observed_end), observed_end, start+max_seconds)
    proposed = max(end, padded)
    try:
        validate_story_boundary({'source_start': start, 'source_end': proposed}, context)
    except ValueError:
        return {'source_end': end, 'reason': 'unsafe_source_word_boundary', 'resolved': False}
    return {'source_end': proposed, 'speech_end': speech_end,
            'reason': 'source_sentence_boundary_with_speech_tail', 'resolved': True}


def validate_story_boundary(plan: dict, context: dict, *, tolerance: float = 1e-6) -> dict:
    if set(plan) != {'source_start', 'source_end'}:
        raise ValueError('Invalid story boundary fields')
    start, end = plan['source_start'], plan['source_end']
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end)) or not 0 <= start < end:
        raise ValueError('Invalid story boundary')
    segments = _all_segments(context)
    if not 0 <= tolerance <= .005001:
        raise ValueError('Invalid boundary compatibility tolerance')
    if not segments or start < min(s['source_start'] for s in segments)-tolerance or end > max(s['source_end'] for s in segments)+tolerance:
        raise ValueError('Boundary outside observed source context')
    for segment in segments:
        for word in segment.get('words', []):
            if word['source_start'] < end and word['source_end'] > start:
                if word['source_start'] < start-tolerance or word['source_end'] > end+tolerance:
                    raise ValueError('Story boundary cuts a source word')
    return {'valid': True, 'source_start': start, 'source_end': end, 'word_timing_available': any(s.get('words') for s in segments)}


def assess_story(context: dict, policy: dict, model_result: dict | None) -> dict:
    text = context.get('text', '')
    folded = _fold(text)
    sentences = [s for s in re.split(r'[.!?\n]+', folded) if s.strip()]
    promotions = sum(bool(PROMOTION.search(s)) for s in sentences)
    dominant = bool(sentences) and promotions > len(sentences)/2
    from .narrative import inspect
    narrative, narrative_extension = inspect(context, max_seconds=policy.get('max_seconds', 60))
    incomplete = bool(DANGLING.search(folded)) or bool(narrative['blocking_obligations'])
    segments = _all_segments(context)
    result = {'schema_version': '1.0', 'rule_version': 'story-v2', 'narrative': narrative,
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
            if model_result['closure'] == 'COMPLETE' and not any(
                    e['source_end'] >= context['source_range']['end']-.05
                    and next(s for s in segments if s['segment_id'] == e['segment_id'])['text'].rstrip().endswith(e['quote'].rstrip())
                    for e in anchored):
                raise ValueError('Missing ending evidence')
            if model_result['closure'] == 'COMPLETE':
                if narrative['open_obligations'] and not narrative['blocking_obligations']:
                    raise ValueError('Question response requires semantic evidence')
                validate_story_boundary({'source_start': context['source_range']['start'],
                                         'source_end': context['source_range']['end']}, context)
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
        if narrative['blocking_obligations']:
            if narrative_extension is not None:
                try:
                    validate_story_boundary({'source_start': start, 'source_end': narrative_extension}, context)
                    result.update(proposed_source_end=narrative_extension,
                                  extension_reason='related_source_response_requires_review')
                except ValueError:
                    pass
            return result
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
        boundary = safe_source_end(context, max_seconds=max_seconds)
        if boundary['source_end'] > clip['end']:
            clip['baseline_window'] = {'start': clip['start'], 'end': clip['end']}
            clip['end'] = boundary['source_end']
            context = build_candidate_context(job, index, {'segments': segments})
        story = assess_story(context, {'max_seconds': max_seconds}, None)
        if story['proposed_source_end'] is not None:
            clip.setdefault('baseline_window', {'start': clip['start'], 'end': clip['end']})
            clip['end'] = story['proposed_source_end']
            context = build_candidate_context(job, index, {'segments': segments})
            boundary = safe_source_end(context, max_seconds=max_seconds)
            clip['end'] = boundary['source_end']
            context = build_candidate_context(job, index, {'segments': segments})
            story = assess_story(context, {'max_seconds': max_seconds}, None)
            story['boundary_adjusted'] = True
        story['boundary_reason'] = boundary['reason']
        story['boundary_adjusted'] = 'baseline_window' in clip
        if not boundary['resolved']:
            story['closure'] = 'INCOMPLETE'
        clip.update(editorial_context=context, text=context['text'], editorial_policy=policy or {'brief': None},
                    story_assessment=story)
        clip['editorial_penalty'] = (50 if story['relevance'] == 'SELF_PROMOTION_DOMINANT' else 0) + (40 if story['closure'] == 'INCOMPLETE' else 0)
    return sorted(output, key=lambda c: c['editorial_penalty'])


def prepare_source_end_revision(job: dict, index: int, transcript: dict, *, assets: dict | None = None,
                                editorial_title: str | None = None) -> dict:
    """Prepare a reviewable replacement plan without touching persisted history.

    The caller must create an explicit render revision and use register_render;
    this function performs no writes, approval or scheduling. Assemblies require
    their own segment-by-segment editorial revision and are deliberately refused.
    """
    from .editorial_context import build_candidate_context
    from .timeline import build_timeline
    previous = job['candidates'][index]
    if previous.get('assembly') or previous.get('timeline', {}).get('schema_version') == '3.0':
        raise ValueError('Assembly ending requires an explicit segment revision')
    context = build_candidate_context(job, index, transcript)
    boundary = safe_source_end(context, max_seconds=job.get('settings', {}).get('max_seconds', 60))
    if not boundary['resolved']:
        raise ValueError('Cannot prepare source ending revision: ' + boundary['reason'])
    if boundary['source_end'] <= previous['end']:
        raise ValueError('No source ending correction available within observed context')
    clip = {key: copy.deepcopy(previous[key]) for key in
            ('start', 'end', 'duration_mode', 'framing', 'framing_schedule') if key in previous}
    clip['end'] = boundary['source_end']
    context = build_candidate_context({'candidates': [clip]}, 0, transcript)
    validate_story_boundary({'source_start': clip['start'], 'source_end': clip['end']}, context)
    story = assess_story(context, {'max_seconds': job.get('settings', {}).get('max_seconds', 60)}, None)
    if story['closure'] == 'INCOMPLETE':
        raise ValueError('Source ending still has an unresolved promised payoff')
    story.update(boundary_reason=boundary['reason'], boundary_adjusted=True)
    clip.update(text=context['text'], editorial_context=context, story_assessment=story,
                baseline_window={'start': previous['start'], 'end': previous['end']})
    layers = previous.get('timeline', {}).get('layers', {})
    if layers.get('broll') and assets is None:
        raise ValueError('Existing B-roll requires the registered asset library for revision')
    edit = {key: copy.deepcopy(layers.get(key, [])) for key in ('effects', 'broll')}
    titles = layers.get('text', [])
    if titles:
        edit['hook'] = titles[0].get('text', '')
        if editorial_title is None and titles[0].get('origin') == 'human':
            editorial_title = titles[0].get('text', '')
    clip['timeline'] = build_timeline(clip, transcript['segments'], edit=edit, assets=assets,
                                      editorial_title=editorial_title)
    return {'parent_candidate_id': previous.get('candidate_id'),
            'parent_candidate_version': previous.get('candidate_version'),
            'parent_artifact_id': previous.get('artifact_id'),
            'parent_render_revision': previous.get('render_revision'),
            'boundary': boundary, 'clip': clip}
