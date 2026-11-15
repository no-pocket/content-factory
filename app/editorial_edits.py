"""Validated, human-authored changes to a reviewed candidate timeline."""
from __future__ import annotations

import copy
import math

from .editorial_context import build_candidate_context
from .editorial_story import assess_story, validate_story_boundary
from .framing import validate_framing_schedule
from .timeline import build_timeline, validate_timeline


def _finite(value, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'Invalid {name}')
    return float(value)


def _caption_source_range(word: dict, timeline: dict) -> tuple[float, float]:
    if timeline['schema_version'] == '3.0':
        return _finite(word.get('source_start'), 'caption source start'), _finite(word.get('source_end'), 'caption source end')
    offset = _finite(timeline['source_range']['start'], 'source range start')
    return offset + _finite(word.get('start'), 'caption start'), offset + _finite(word.get('end'), 'caption end')


def prepare_timeline_edit(job: dict, index: int, transcript: dict, changes: dict, *, assets: dict | None = None) -> dict:
    """Apply a strict edit patch and return a replacement plan without writing files."""
    allowed = {'source_start', 'source_end', 'title', 'caption_overrides', 'framing_schedule'}
    if not isinstance(changes, dict) or not changes or set(changes) - allowed:
        raise ValueError('Invalid timeline edit fields')
    clip = copy.deepcopy(job['candidates'][index])
    timeline = copy.deepcopy(clip.get('timeline'))
    if not isinstance(timeline, dict):
        raise ValueError('Candidate has no editable timeline')
    validate_timeline(timeline)
    if timeline['schema_version'] not in {'2.0', '3.0'}:
        raise ValueError('Unsupported candidate timeline')

    range_changed = 'source_start' in changes or 'source_end' in changes
    if range_changed:
        if timeline['schema_version'] != '2.0':
            raise ValueError('Trim edits require a contiguous source timeline')
        prior_timeline = timeline
        start = _finite(changes.get('source_start', clip['start']), 'source start')
        end = _finite(changes.get('source_end', clip['end']), 'source end')
        duration = end - start
        settings = job.get('settings') or {}
        mode = settings.get('duration_mode', 'classic')
        minimum = _finite(settings.get('min_seconds', 0), 'minimum duration')
        maximum = _finite(settings.get('max_seconds', 60 if mode != 'flexible' else 180), 'maximum duration')
        if not 0 <= start < end or not minimum <= duration <= maximum:
            raise ValueError('Trim is outside the saved duration bounds')
        clip.update(start=start, end=end)
        context = build_candidate_context({'candidates': [clip]}, 0, transcript)
        validate_story_boundary({'source_start': start, 'source_end': end}, context)
        clip.update(editorial_context=context, text=context['text'])
        clip.pop('model_story', None)
        story = assess_story(context, {'max_seconds': maximum}, None)
        if story['closure'] == 'INCOMPLETE':
            raise ValueError('Trim leaves an unresolved ending; extend the range or choose another cut')
        clip['story_assessment'] = story
        layers = timeline['layers']
        prior_title = next((item for item in layers['text'] if item.get('text')), None)
        edit = {'effects': copy.deepcopy(layers['effects']), 'broll': copy.deepcopy(layers['broll'])}
        if prior_title:
            edit['hook'] = prior_title['text']
        human_title = prior_title['text'] if prior_title and prior_title.get('origin') == 'human' else None
        prior_captions = [
            (_caption_source_range(word, prior_timeline), word['text'])
            for word in layers['captions']
        ]
        clip.pop('framing', None)
        clip.pop('framing_schedule', None)
        if prior_timeline.get('framing'):
            clip['framing'] = copy.deepcopy(prior_timeline['framing'])
        if prior_timeline.get('framing_schedule'):
            prior_start = _finite(prior_timeline['source_range']['start'], 'source range start')
            remapped_schedule = []
            for window in prior_timeline['framing_schedule']:
                source_start = max(start, prior_start + window['start'])
                source_end = min(end, prior_start + window['end'])
                if source_start < source_end:
                    remapped_schedule.append({
                        **copy.deepcopy(window),
                        'start': source_start - start,
                        'end': source_end - start,
                    })
            clip['framing_schedule'] = remapped_schedule
        timeline = build_timeline(
            clip, transcript['segments'], edit=edit, assets=assets or {},
            editorial_title=human_title,
        )
        for (source_start, source_end), text in prior_captions:
            matches = [
                word for word in timeline['layers']['captions']
                if all(abs(actual - wanted) <= 0.002 for actual, wanted in
                       zip(_caption_source_range(word, timeline), (source_start, source_end)))
            ]
            if len(matches) == 1:
                matches[0]['text'] = text
        clip['timeline'] = timeline

    timeline = copy.deepcopy(clip['timeline'])
    layers = timeline['layers']

    if 'title' in changes:
        title = changes['title']
        if (not isinstance(title, str) or len(title) > 80 or len(title.split()) > 12
                or any(ord(c) < 32 for c in title) or (title.strip() and not any(c.isalpha() for c in title))):
            raise ValueError('Title must be at most 80 characters and 12 words')
        title = ' '.join(title.split())
        if title:
            banner = next((item for item in layers['text'] if item.get('text')), None)
            if banner is None:
                banner = {'at': 0.5, 'duration': min(2.5, max(0.6, timeline['duration'] - 0.6)),
                          'animation': 'pop', 'style': 'compact_editorial_v1'}
                layers['text'] = [banner]
            banner.update(text=title, origin='human')
        else:
            layers['text'] = []

    overrides = changes.get('caption_overrides', [])
    if not isinstance(overrides, list) or len(overrides) > 2000:
        raise ValueError('Invalid caption corrections')
    seen = set()
    for override in overrides:
        if not isinstance(override, dict) or set(override) != {'source_start', 'source_end', 'text'}:
            raise ValueError('Invalid caption correction fields')
        start = _finite(override['source_start'], 'caption correction start')
        end = _finite(override['source_end'], 'caption correction end')
        text = override['text']
        key = (round(start, 3), round(end, 3))
        if key in seen or not isinstance(text, str) or not text.strip() or len(text) > 64 or any(ord(c) < 32 for c in text):
            raise ValueError('Invalid or duplicate caption correction')
        seen.add(key)
        matches = [word for word in layers['captions']
                   if all(abs(actual - wanted) <= 0.002 for actual, wanted in
                          zip(_caption_source_range(word, timeline), (start, end)))]
        if len(matches) != 1:
            raise ValueError('Caption correction no longer matches a source word; reload the editor')
        matches[0]['text'] = text.strip()

    if 'framing_schedule' in changes:
        schedule = validate_framing_schedule(changes['framing_schedule'], timeline['duration'])
        timeline['framing_schedule'] = schedule

    validate_timeline(timeline)
    clip['timeline'] = timeline
    return {'clip': clip, 'boundary': {
        'source_start': clip.get('start'), 'source_end': clip.get('end'),
        'reason': 'human_confirmed_timeline_edit',
    }}
