"""One-source narrative assembly with a frame-count clock and word provenance."""
from __future__ import annotations

import copy
from fractions import Fraction
import math
import re

FPS = 30


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Invalid assembly time')
    return value


def validate_assembly(plan: dict, source_duration: float) -> dict:
    if isinstance(plan, dict) and plan.get('schema_version') == '2.0':
        from .timeline import validate_timeline
        validate_timeline(plan)
        return copy.deepcopy(plan)
    allowed = {'schema_version', 'source_duration', 'segments', 'fps', 'duration', 'reorder_approval'}
    if not isinstance(plan, dict) or set(plan)-allowed or plan.get('schema_version') != '3.0':
        raise ValueError('Invalid assembly schema')
    _number(source_duration)
    if source_duration <= 0 or plan.get('fps', FPS) != FPS:
        raise ValueError('Invalid assembly source/fps')
    if 'source_duration' in plan and plan['source_duration'] != source_duration:
        raise ValueError('Assembly source duration mismatch')
    segments = plan.get('segments')
    if not isinstance(segments, list) or not 1 <= len(segments) <= 12:
        raise ValueError('Assembly requires 1..12 nonempty segments')
    result, ids, frames = [], set(), 0
    for segment in segments:
        keys = {'segment_id', 'source_in', 'source_out', 'output_start', 'purpose', 'framing', 'frame_count', 'duration'}
        if not isinstance(segment, dict) or set(segment)-keys or not {'segment_id','source_in','source_out','purpose'} <= set(segment):
            raise ValueError('Invalid assembly segment fields')
        ident = segment['segment_id']
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,50}', ident) or ident in ids:
            raise ValueError('Invalid/duplicate assembly segment ID')
        ids.add(ident)
        start, end = _number(segment['source_in']), _number(segment['source_out'])
        if not 0 <= start < end <= source_duration:
            raise ValueError('Assembly segment outside source or empty')
        if any(max(start, s['source_in']) < min(end, s['source_out']) for s in result):
            raise ValueError('Assembly source segments overlap')
        if result and start < result[-1]['source_out']:
            approval = plan.get('reorder_approval')
            if not isinstance(approval, dict) or set(approval) != {'kind','actor'} or approval['kind'] != 'human' or not isinstance(approval['actor'],str) or not approval['actor'].strip():
                raise ValueError('Nonchronological assembly requires explicit human approval')
        if not isinstance(segment['purpose'], str) or not 0 < len(segment['purpose']) <= 300:
            raise ValueError('Segment purpose required')
        count = math.ceil((Fraction(str(end))-Fraction(str(start)))*FPS)
        output_start = frames/FPS
        if 'output_start' in segment and abs(_number(segment['output_start'])-output_start) > 1e-7:
            raise ValueError('Noncontiguous assembly output clock')
        if 'frame_count' in segment and (type(segment['frame_count']) is not int or segment['frame_count'] != count):
            raise ValueError('Invalid segment frame count')
        if 'duration' in segment and abs(_number(segment['duration'])-count/FPS) > 1e-7:
            raise ValueError('Invalid segment output duration')
        clean = {**copy.deepcopy(segment), 'output_start': output_start, 'frame_count': count, 'duration': count/FPS}
        if 'framing' in clean:
            from .framing import validate_scene
            clean['framing'] = validate_scene(clean['framing'])
        result.append(clean)
        frames += count
    if frames > 120*FPS:
        raise ValueError('Assembly exceeds 120 seconds')
    duration = frames/FPS
    if 'duration' in plan and abs(_number(plan['duration'])-duration) > 1e-7:
        raise ValueError('Assembly duration does not match its frame clock')
    return {**copy.deepcopy(plan), 'source_duration': source_duration, 'segments': result, 'fps': FPS, 'duration': duration}


def map_words(plan: dict, words: list[dict]) -> list[dict]:
    plan = validate_assembly(plan, plan['source_duration'])
    mapped = []
    for index, word in enumerate(words):
        start, end = _number(word['start']), _number(word['end'])
        if not 0 <= start < end <= plan['source_duration']:
            raise ValueError('Invalid source word timing')
        text = word.get('text', word.get('word', ''))
        if not isinstance(text, str) or not text.strip() or len(text) > 500:
            raise ValueError('Invalid source word text')
        for segment in plan['segments']:
            if start < segment['source_out'] and end > segment['source_in']:
                if start < segment['source_in']-1e-7 or end > segment['source_out']+1e-7:
                    raise ValueError('Assembly cuts a partial source word')
                mapped.append({'start': segment['output_start']+start-segment['source_in'],
                               'end': segment['output_start']+end-segment['source_in'], 'text': text.strip(),
                               'word_id': word.get('word_id', str(index)), 'segment_id': segment['segment_id'],
                               'source_start': start, 'source_end': end})
    return sorted(mapped, key=lambda w:(w['start'],w['end']))
