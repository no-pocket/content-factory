"""Optional advisory critique. No transport, execution, timeline or review authority."""
from __future__ import annotations

import copy
import math

from .artifacts import digest


def validate_critique(payload: dict, context: dict) -> dict:
    if not isinstance(payload,dict) or set(payload)!={'schema_version','uncertainty','suggestions'} or payload['schema_version']!='1.0':
        raise ValueError('Invalid critique fields/version')
    if not isinstance(payload['uncertainty'],str) or not 1<=len(payload['uncertainty'])<=2000:
        raise ValueError('Critique uncertainty required')
    if not isinstance(payload['suggestions'],list) or len(payload['suggestions'])>8:
        raise ValueError('Invalid critique suggestions')
    source = context.get('before',[])+context.get('segments',[])+context.get('after',[])
    if not source:
        raise ValueError('Source context required')
    lower, upper = min(s['source_start'] for s in source), max(s['source_end'] for s in source)
    clean = copy.deepcopy(payload)
    for item in clean['suggestions']:
        common = {'kind','reason','evidence'}
        variant = {'BOUNDARY':{'source_start','source_end'},'FRAMING':{'framing'},'TITLE':{'title'}}
        if not isinstance(item,dict) or item.get('kind') not in variant or set(item)!=common|variant[item['kind']]:
            raise ValueError('Critique cannot set files, commands, timelines or human decisions')
        if not isinstance(item['reason'],str) or not 1<=len(item['reason'])<=2000:
            raise ValueError('Suggestion reason required')
        if not isinstance(item['evidence'],list) or not 1<=len(item['evidence'])<=8:
            raise ValueError('Source evidence required')
        for evidence in item['evidence']:
            if not isinstance(evidence,dict) or set(evidence)!={'segment_id','quote'} or type(evidence['segment_id']) is not int:
                raise ValueError('Invalid critique evidence')
            quote=evidence['quote']
            segment=next((s for s in source if s['segment_id']==evidence['segment_id'] and
                          isinstance(quote,str) and quote in s['text']),None)
            if segment is None or not quote.strip() or len(quote)>1000:
                raise ValueError('Critique evidence not anchored to source')
            evidence.update(source_start=segment['source_start'],source_end=segment['source_end'])
        if item['kind']=='BOUNDARY':
            start,end=item['source_start'],item['source_end']
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (start,end)) or not lower<=start<end<=upper:
                raise ValueError('Critique boundary outside source context')
            from .editorial_story import validate_story_boundary
            validate_story_boundary({'source_start':start,'source_end':end},context)
        elif item['kind']=='FRAMING':
            from .framing import validate_scene
            item['framing']=validate_scene(item['framing'])
        elif item['kind']=='TITLE':
            from .editorial_context import validate_title
            result=validate_title(item['title'],{'text':' '.join(s['text'] for s in source)})
            if not result['valid']:
                raise ValueError('Critique title lacks evidence')
    return clean


def critique_plan(context: dict, plan: dict, *, capability: dict | None=None,
                  transport=None, dry_run: bool=True) -> dict:
    """Injected transport is for an explicitly configured executor or synthetic tests.

    The available Hermes MCP is messaging only. It is not used as an executor and
    this module never discovers a random conversation or sends content to one.
    """
    result={'baseline':copy.deepcopy(plan),'critique':None,'sent':False,
            'plan_sha256':digest(plan),'context_sha256':digest(context)}
    capability=capability or {}
    if not capability.get('execution') or not capability.get('structured_response'):
        return {**result,'status':'UNAVAILABLE','reason':'No verified structured task execution capability; local direction retained'}
    if dry_run:
        return {**result,'status':'DRY_RUN','reason':'No content sent; external comparison and human evaluation not performed'}
    if transport is None:
        return {**result,'status':'UNAVAILABLE','reason':'No explicitly configured task transport'}
    request={'schema_version':'1.0','context':copy.deepcopy(context),'local_plan':copy.deepcopy(plan),
             'modality':'text_and_frames' if capability.get('vision') else 'text_only'}
    try:
        payload=transport(request)
        critique=validate_critique(payload,context)
        return {**result,'status':'ADVISORY_ONLY','sent':True,'critique':critique,'modality':request['modality']}
    except (OSError,ValueError,TypeError,KeyError,TimeoutError) as exc:
        return {**result,'status':'FALLBACK','sent':True,'reason':type(exc).__name__+'; local direction retained'}
