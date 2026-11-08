"""Auditable PT/EN discourse cues, not a semantic model or human judgement.

Promises/questions remain open until an observed related response. Resolution
only removes a veto; it never establishes that a clip is narratively COMPLETE.
"""
import re
import unicodedata


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


PROMISE = re.compile(r"\b(?:vou|vamos) (?:mostrar|explicar|revelar|demonstrar)\b|\b(?:i will|i'll|we will|we'll|let me) (?:show|explain|reveal|demonstrate)\b")
QUESTION = re.compile(r'^(?:por que|qual|quais|why|what|which|how (?:does|do|did|can|will|is)|como (?:funciona|sera|vai|ficou|pode))\b')
RHETORICAL = re.compile(r"^(?:what['’]?s up|how are you)\b|\b(?:ne|right|isn['’]?t it)[?\s]*$")
PAYOFF = re.compile(r'\b(?:aqui esta|aqui vemos|mostra|demonstra|revela|here is|here we see|shows|demonstrates|reveals)\b')
ANSWER = re.compile(r'^(?:porque|a resposta|because|the answer)\b')
TRANSITION = re.compile(r'\b(?:mudando de assunto|outro assunto|proximo assunto|moving on|next topic|in other news|subscribe|inscreva|meu canal|my channel)\b')
STOP = set('o a os as um uma de do da dos das que e em no na para por com the a an of to in on with you eu nos voce agora now this that is will vou vamos mostrar explicar revelar demonstrar show explain reveal demonstrate let me i we why how what which por porque como qual quais'.split())


def subjects(text):
    return {w for w in re.findall(r'\w+', fold(text)) if len(w) > 2 and w not in STOP}


def units(context):
    """Sentence observations on the source clock; never borrow unheard words."""
    start = context['source_range']['start']
    result = []
    for segment in sorted(context.get('segments', []) + context.get('after', []), key=lambda s: s['source_start']):
        words = segment.get('words')
        complete_word_text = ' '.join(w['text'] for w in words or [])
        if words and fold(complete_word_text).split() == fold(segment['text']).split():
            pending = []
            for word in words:
                if word['source_start'] < start:
                    continue
                pending.append(word)
                if re.search(r'[.!?]["\'”’)]*$', word['text'].strip()):
                    result.append({'text': ' '.join(w['text'] for w in pending),
                                   'source_end': word['source_end'], 'segment_id': segment['segment_id']})
                    pending = []
            if pending:
                result.append({'text': ' '.join(w['text'] for w in pending),
                               'source_end': pending[-1]['source_end'], 'segment_id': segment['segment_id']})
        elif segment['source_start'] >= start:
            # Without word clocks all sentence observations share the segment end.
            for text in re.findall(r'[^.!?]+[.!?]*', segment['text']):
                if text.strip():
                    result.append({'text': text.strip(), 'source_end': segment['source_end'],
                                   'segment_id': segment['segment_id']})
    return result


def analyze(observations):
    pending, resolved = [], []
    for unit in observations:
        text = fold(unit['text']).strip()
        promise = PROMISE.search(text)
        if promise and re.search(r'\b(?:nao|not|never)\s*$', text[:promise.start()]):
            promise = None
        question = text.endswith('?') and QUESTION.search(text) and not RHETORICAL.search(text)
        if not promise and not question:
            remaining = []
            for obligation in pending:
                related = bool(subjects(text) & set(obligation['subjects']))
                payoff_marker = PAYOFF.search(text)
                negated_payoff = bool(payoff_marker and re.match(
                    r'\s+(?:(?:actually|definitely|realmente)\s+)?(?:not|never|nao)\b',
                    text[payoff_marker.end():]))
                payoff = bool(payoff_marker) and not negated_payoff and (related or not obligation['subjects'])
                # A causal marker alone could answer an entirely different question.
                answer = obligation['kind'] == 'question' and bool(ANSWER.search(text)) and related
                if (payoff or answer) and not TRANSITION.search(text):
                    resolved.append({'opening': obligation, 'response': dict(unit)})
                else:
                    if obligation['kind'] == 'question' and not TRANSITION.search(text):
                        obligation['possible_response_observed'] = True
                    remaining.append(obligation)
            pending = remaining
        if promise or question:
            subject = text[promise.end():] if promise else text
            pending.append({**unit, 'kind': 'promise' if promise else 'question',
                            'subjects': sorted(subjects(subject))})
    return {'rule_version': 'discourse-cues-v1', 'open_obligations': pending,
            'blocking_obligations': [o for o in pending if o['kind'] == 'promise'],
            'observed_resolutions': resolved, 'semantic_completion_proven': False}


def inspect(context, *, max_seconds):
    observations = units(context)
    end, start = context['source_range']['end'], context['source_range']['start']
    current = [u for u in observations if u['source_end'] <= end]
    diagnosis = analyze(current)
    extension = None
    if diagnosis['blocking_obligations']:
        for unit in observations:
            if unit['source_end'] <= end:
                continue
            if unit['source_end'] - start > max_seconds or TRANSITION.search(fold(unit['text'])):
                break
            current.append(unit)
            if not analyze(current)['blocking_obligations']:
                extension = unit['source_end']
                break
    return diagnosis, extension
