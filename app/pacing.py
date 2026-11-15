"""Bounded speech pacing from native ASR timestamps, never forced alignment."""
from __future__ import annotations
import copy
from .assembly import validate_assembly, map_words, build_assembly_context, native_word_groups


def pace_plan(plan: dict, segments: list[dict], *, min_seconds: float, preference='auto') -> tuple[dict, dict]:
    if preference not in ('auto','natural'):
        raise ValueError('Invalid pacing preference')
    plan=validate_assembly(plan,plan['source_duration'])
    segments=native_word_groups(segments)
    words=map_words(plan,[w for s in segments for w in s.get('words',[])])
    source_seconds=sum(s['source_out']-s['source_in'] for s in plan['segments'])
    count=sum(len(w['text'].split()) for w in words)
    wpm=60*count/source_seconds
    desired=1.15 if wpm<100 else 1.1 if wpm<125 else 1
    if preference=='natural' or count<20:
        desired=1
    allowed=source_seconds/min_seconds if min_seconds>0 else 1.15
    rate=max(r for r in (1,1.05,1.1,1.15) if r<=max(1,min(desired,allowed)))
    pieces=[{k:v for k,v in s.items() if k not in ('output_start','frame_count','duration','playback_rate')}
            for s in plan['segments']]
    if rate>1:
        for piece in pieces: piece['playback_rate']=rate
    result=validate_assembly({**{k:v for k,v in plan.items() if k not in ('segments','duration')},'segments':pieces},plan['source_duration'])
    return result,{'rate':rate,'words_per_minute':round(wpm,1),'word_count':count,
        'zero_duration_words_grouped':sum(w.get('zero_duration_word_count',0) for w in words),
        'source_seconds':round(source_seconds,3),'output_seconds':result['duration'],
        'reason':'observed_slow_speech' if rate>1 else 'natural_or_insufficient_evidence',
        'method':'native_word_timestamps_v1'}


def apply_candidate_pacing(clip, segments, source_duration, settings, *, preference='auto') -> float:
    if not settings.get('auto_pace',False) or clip.get('assembly'):
        return 1
    if clip['end']-clip['start']>120:
        clip['pace']={'rate':1,'words_per_minute':None,'reason':'contiguous_over_120_seconds'}
        return 1
    plan={'schema_version':'3.0','source_duration':source_duration,'segments':[
        {'segment_id':'speech','source_in':clip['start'],'source_out':clip['end'],'purpose':'Fala original com ritmo ajustado'}]}
    try:
        plan,diagnostic=pace_plan(plan,segments,min_seconds=settings['min_seconds'],preference=preference)
    except ValueError:
        clip['pace']={'rate':1,'words_per_minute':None,'reason':'native_timing_unavailable'}
        return 1
    clip['pace']=diagnostic
    if diagnostic['rate']>1 or diagnostic.get('zero_duration_words_grouped',0):
        clip['assembly']=plan
        clip['editorial_context']=build_assembly_context(plan,segments)
        if settings.get('framing_windows'):
            from .framing import build_framing_schedule
            clip['framing_schedule']=build_framing_schedule(clip,settings)
        return diagnostic['rate']
    return 1


def retime_hints(hints: dict, rate: float) -> dict:
    if rate==1:return hints
    result=copy.deepcopy(hints)
    for kind in ('effects','broll'):
        for item in result.get(kind,[]):
            if type(item.get('at')) in (int,float): item['at']/=rate
    return result
