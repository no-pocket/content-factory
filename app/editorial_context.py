"""Source-anchored context and explicit prompt/title validation."""
from __future__ import annotations

import math
import re
import unicodedata

from .artifacts import digest


def build_candidate_context(job: dict, index: int, transcript: dict, *, before_seconds: float = 12,
                            after_seconds: float = 15) -> dict:
    clip = job['candidates'][index]
    start, end = clip['start'], clip['end']
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in (start, end, before_seconds, after_seconds)) or not 0 <= start < end or min(before_seconds, after_seconds) < 0:
        raise ValueError('Invalid context boundaries')
    groups = {'segments': [], 'before': [], 'after': []}
    for position, segment in enumerate(transcript['segments']):
        a, b = segment['start'], segment['end']
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (a, b)) or not 0 <= a < b:
            raise ValueError('Invalid transcript segment')
        item = {'segment_id': position, 'source_start': a, 'source_end': b, 'text': str(segment.get('text', '')),
                'candidate_start': a-start, 'candidate_end': b-start}
        item['words'] = [{'word_id': f'{position}:{word_index}', 'source_start': word['start'],
                          'source_end': word['end'], 'text': word.get('text', word.get('word', ''))}
                         for word_index, word in enumerate(segment.get('words', []))]
        if a < end and b > start:
            groups['segments'].append(item)
        elif b <= start and b > start-before_seconds:
            groups['before'].append(item)
        elif a >= end and a < end+after_seconds:
            groups['after'].append(item)
    text = ' '.join(s['text'] for s in groups['segments']).strip()
    return {'schema_version': '1.0', 'source_range': {'start': start, 'end': end}, **groups,
            'text': text, 'transcript_sha256': digest(transcript),
            'source_sha256': job.get('source_fingerprint', 'UNKNOWN'),
            'coverage': {'complete_candidate': bool(groups['segments']), 'prefix_truncated': False,
                         'before_seconds': before_seconds, 'after_seconds': after_seconds},
            'context_sha256': digest({'range': [start, end], **groups})}


def require_prompt_budget(prompt: str, *, context_window: int = 4096, reserve: int = 700) -> dict:
    """Conservative preflight; GPU bridge additionally checks the live ChatML tokenizer.

    Byte-level tokenizers cannot produce more text tokens than UTF-8 bytes. Reserve
    256 for template/special tokens. This bound may reject a prompt that would fit;
    it never silently drops its ending or claims to be an exact tokenizer count.
    """
    if type(context_window) is not int or type(reserve) is not int or not 0 < reserve < context_window:
        raise ValueError('Invalid context budget')
    upper = len(prompt.encode('utf-8')) + 256
    if upper + reserve > context_window:
        raise ValueError(f'Prompt budget exceeded: byte upper bound {upper} + reserve {reserve} > {context_window}; full context retained, inference skipped')
    return {'method': 'utf8_byte_upper_bound', 'prompt_upper_bound': upper, 'generation_reserve': reserve,
            'context_window': context_window, 'prefix_truncated': False}


def compact_source_context(context: dict) -> dict:
    """Lossless segment table for models; word timing stays in stored context.

    All before/candidate/after text, source times and IDs remain available. Arrays
    avoid repeating long field names and per-word metadata in every neighbor.
    """
    fields = ('segment_id', 'source_start', 'source_end', 'text')
    return {'fields': list(fields), 'source_range': dict(context['source_range']),
            **{group: [[segment[key] for key in fields] for segment in context[group]]
               for group in ('before', 'segments', 'after')}}


def _tokens(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    return re.findall(r'\w+', ''.join(c for c in text if not unicodedata.combining(c)))


def validate_title(title: str, evidence: dict) -> dict:
    if not isinstance(title, str):
        return {'valid': False, 'reason': 'title_not_text', 'normalized': ''}
    normalized = ' '.join(title.split())
    tokens = _tokens(normalized)
    source = _tokens(evidence.get('text', ''))
    reason = None
    if not normalized or len(normalized) > 80 or len(tokens) > 12 or not any(c.isalpha() for c in normalized) or any(ord(c) < 32 for c in title):
        reason = 'invalid_title_text'
    elif tokens == source[:len(tokens)]:
        reason = 'transcript_echo'
    elif _claim_modifiers(tokens) != _claim_modifiers(source):
        reason = 'unsupported_title_polarity'
    elif not _grounded_title(tokens, evidence.get('text', '')):
        reason = 'unsupported_title_relation'
    return {'valid': reason is None, 'reason': reason, 'normalized': normalized}


def _grounded_title(tokens: list[str], source_text: str) -> bool:
    # Fail closed: match one contiguous, ordered content phrase in one clause.
    # Only grammatical scaffolding and the documented inflections are removed;
    # another verb/object cannot be skipped to assemble a new relationship.
    function_words = set('como por porque para quando onde qual quais que uma uns umas seu sua seus suas esse essa isso este esta the how why what to of a an and in on with voce deve consiste'.split())
    aliases = {'vendendo':'vender', 'venda':'vender', 'ganhando':'ganhar',
               'ganho':'ganhar', 'comprando':'comprar', 'compra':'comprar',
               'selling':'sell', 'buying':'buy', 'earning':'earn'}
    def canonical(t):
        t = aliases.get(t, t)
        return t[:-1] if len(t) > 4 and t.endswith('s') else t
    def content(words):
        return [canonical(t) for t in words if t not in function_words and (len(t)>3 or t.isdigit())]
    wanted = content(tokens)
    if not wanted:
        return False
    # Explicit repeated-subject descriptor carryover: "mapa de GTA 6. O mapa
    # revela Vice City" may retain the same map's identifier. No verbs, objects
    # or general previous-sentence word bags are carried into the next clause.
    descriptors = {}
    clauses = re.split(r'[.!?;:,]+|\b(?:e|and|mas|but|enquanto|although)\b', source_text, flags=re.IGNORECASE)
    for clause in clauses:
        normalized = ' '.join(_tokens(clause))
        first = re.match(r'^(?:(?:o|a|the) )?(\w+)\b', normalized)
        if first and first.group(1) in descriptors:
            subject = first.group(1)
            normalized = normalized[:first.start(1)] + descriptors[subject] + normalized[first.end(1):]
        available = content(normalized.split())
        if any(available[i:i+len(wanted)] == wanted for i in range(len(available)-len(wanted)+1)):
            return True
        # A descriptor is limited to noun + de/of + capitalized identifier and
        # optional number. It must be repeated as the next clause's subject.
        descriptors = {}
        for match in re.finditer(r'\b(\w+)\s+(?:de|of)\s+([A-Z][A-Za-z0-9_]*(?:\s+\d+)?)\b', clause):
            descriptors[_tokens(match.group(1))[0]] = ' '.join(_tokens(match.group(0)))
    return False


def _claim_modifiers(tokens: list[str]) -> tuple[bool, bool]:
    # Deliberately conservative across the whole selected passage: no attempt
    # to infer negation scope, sarcasm or semantic entailment from word overlap.
    words = set(tokens)
    negative = bool(words & {'nao', 'nunca', 'jamais', 'nem', 'not', 'never', 'cannot', 'without'})
    uncertain = bool(words & {'talvez', 'possivelmente', 'provavelmente', 'pode', 'possa',
        'poderia', 'supostamente', 'rumor', 'rumores', 'hipotese', 'incerto', 'incerta',
        'may', 'might', 'could', 'possibly', 'probably', 'uncertain', 'allegedly', 'rumour', 'rumor'})
    return negative, uncertain
