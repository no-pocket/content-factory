"""Canonical editorial request primitives; no external I/O or job mutation."""
import json
from .artifacts import digest

MAX_PLAN_BYTES = 256 * 1024

def transcript_digest(transcript: dict) -> str:
    return 'sha256:' + digest(transcript)

def segment_id(index: int) -> str:
    if type(index) is not int or not 0 <= index <= 999999:
        raise ValueError('invalid segment index')
    return f'seg-{index:06d}'

def parse_plan(payload: bytes) -> dict:
    if not isinstance(payload, bytes) or len(payload) > MAX_PLAN_BYTES:
        raise ValueError('invalid editorial plan size')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError('non-finite JSON number')
    try:
        result = json.loads(payload.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid editorial plan JSON') from exc
    if not isinstance(result, dict):
        raise ValueError('editorial plan must be an object')
    return result

def validate_editorial_plan(plan: dict, request: dict, transcript: dict) -> dict:
    """Validate identities and source-anchored, bounded editorial outcomes."""
    import copy
    import re
    import uuid
    required = {'schema_version', 'request_id', 'submission_id', 'editorial_attempt_id', 'job_id', 'run_id', 'source', 'transcript', 'planner', 'outcome', 'candidates', 'reason'}
    if isinstance(plan, dict) and plan.get('outcome') == 'candidates_proposed':
        required.remove('reason')
    if not isinstance(plan, dict) or set(plan) != required or plan['schema_version'] != '1.0':
        raise ValueError('invalid editorial envelope')
    for key in ('request_id', 'submission_id', 'editorial_attempt_id', 'job_id', 'run_id'):
        try:
            if not isinstance(plan[key], str) or str(uuid.UUID(plan[key])) != plan[key]:
                raise ValueError('invalid uuid')
        except (ValueError, AttributeError) as exc:
            raise ValueError('invalid editorial identity') from exc
        if key != 'submission_id' and plan[key] != request.get(key):
            raise ValueError('editorial identity mismatch')
    source = plan['source']
    if not isinstance(source, dict) or set(source) != {'source_fingerprint', 'duration_ms'}:
        raise ValueError('invalid source identity')
    if not isinstance(source['source_fingerprint'], str) or not re.fullmatch('[0-9a-f]{64}', source['source_fingerprint']) or source['source_fingerprint'] != request.get('source_fingerprint'):
        raise ValueError('source mismatch')
    if type(source['duration_ms']) is not int or source['duration_ms'] <= 0 or source['duration_ms'] != request.get('duration_ms'):
        raise ValueError('source duration mismatch')
    tx = plan['transcript']
    if not isinstance(tx, dict) or set(tx) != {'digest', 'canonicalization', 'language', 'timebase'} or tx['canonicalization'] != 'cf-transcript-v1' or tx['timebase'] != 'source_ms' or tx['language'] != transcript.get('language') or tx['digest'] != request.get('transcript_digest') or tx['digest'] != transcript_digest(transcript):
        raise ValueError('transcript mismatch')
    planner = plan['planner']
    if not isinstance(planner, dict) or set(planner) != {'engine', 'provider', 'model', 'prompt_version', 'invocation_id'} or planner['engine'] != 'hermes' or any(not isinstance(v, str) or not v.strip() or len(v) > 1000 for v in planner.values()):
        raise ValueError('invalid planner metadata')
    if plan['outcome'] == 'no_suitable_candidates':
        if plan['candidates'] != [] or not isinstance(plan['reason'], str) or not plan['reason'].strip() or len(plan['reason']) > 1000:
            raise ValueError('invalid empty outcome')
    elif plan['outcome'] == 'candidates_proposed':
        candidates = plan['candidates']
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 6:
            raise ValueError('invalid candidates')
        seen = set()
        for candidate in candidates:
            _validate_candidate(candidate, request, transcript, seen)
    else:
        raise ValueError('invalid editorial outcome')
    return copy.deepcopy(plan)


def _validate_candidate(candidate, request, transcript, seen):
    import re
    import unicodedata
    import uuid
    def text(value):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= 1000
    fields = {'proposal_id', 'editorial_title', 'intent', 'segments', 'direction', 'risks'}
    if not isinstance(candidate, dict) or set(candidate) != fields:
        raise ValueError('invalid candidate fields')
    ident = candidate['proposal_id']
    try:
        if not isinstance(ident, str) or str(uuid.UUID(ident)) != ident or ident in seen:
            raise ValueError('invalid proposal id')
    except (ValueError, AttributeError) as exc:
        raise ValueError('invalid proposal id') from exc
    seen.add(ident)
    if not text(candidate['editorial_title']) or not text(candidate['intent']):
        raise ValueError('invalid candidate text')
    segments = candidate['segments']
    if not isinstance(segments, list) or len(segments) != 1:
        raise ValueError('only one continuous segment is supported')
    part = segments[0]
    if not isinstance(part, dict) or set(part) != {'source_in_ms','source_out_ms','start_anchor','end_anchor','boundary_status'}:
        raise ValueError('invalid segment fields')
    start, end = part['source_in_ms'], part['source_out_ms']
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= request['duration_ms'] or not request['min_seconds'] * 1000 <= end-start <= request['max_seconds'] * 1000:
        raise ValueError('segment outside source or duration policy')
    if part['boundary_status'] != 'requires_audio_review':
        raise ValueError('unsupported boundary status')
    def normalized(s):
        return ' '.join(unicodedata.normalize('NFC', s).split())
    for name in ('start_anchor', 'end_anchor'):
        anchor = part[name]
        if not isinstance(anchor, dict) or set(anchor) != {'segment_id','quote'} or not isinstance(anchor['segment_id'], str) or not re.fullmatch(r'seg-[0-9]{6}', anchor['segment_id']) or not text(anchor['quote']):
            raise ValueError('invalid anchor')
        index = int(anchor['segment_id'][4:])
        if index >= len(transcript['segments']):
            raise ValueError('anchor does not exist')
        actual = transcript['segments'][index]
        if normalized(anchor['quote']) not in normalized(actual['text']) or not actual['start'] * 1000 < end or not actual['end'] * 1000 > start:
            raise ValueError('anchor does not match source interval')
    direction = candidate['direction']
    if not isinstance(direction, dict) or set(direction) != {'layout_preset_id','subtitle_preset_id','pacing','word_highlight'} or direction['layout_preset_id'] not in request.get('layout_presets', []) or direction['subtitle_preset_id'] not in request.get('subtitle_presets', []) or direction['pacing'] != 'natural' or direction['word_highlight'] != 'only_if_word_timing_reliable':
        raise ValueError('unsupported direction')
    risks = candidate['risks']
    if not isinstance(risks, list) or len(risks) > 20 or any(not isinstance(r, dict) or set(r) != {'type','detail'} or not text(r['type']) or not text(r['detail']) for r in risks):
        raise ValueError('invalid risks')
