"""Offline, predecision feature extraction. No human outcomes are inputs."""
import math

FEATURES=('duration_seconds','source_position','word_count','llm_relevance','autopromotion_score',
          'closure_complete','promise_delivered','proof_score','hook_score','pause_fraction','visual_protected','repeat_score')


def extract_features(context: dict, plan: dict, signals: dict, versions: dict) -> dict:
    bounds=context.get('source_range',{})
    duration=plan.get('duration')
    if duration is None and {'start','end'}<=set(bounds):duration=bounds['end']-bounds['start']
    supplied={'duration_seconds':duration,'source_position':bounds.get('start'),
              'word_count':len(context['text'].split()) if isinstance(context.get('text'),str) else None,
              **{key:signals.get(key) for key in FEATURES[3:]}}
    values={}
    for key,value in supplied.items():
        if value is not None and (type(value) not in (float,int) or not math.isfinite(value) or value<0):
            raise ValueError('Invalid predecision feature: '+key)
        if key in FEATURES[3:] and value is not None and value>1:
            raise ValueError('Normalized feature outside 0..1: '+key)
        values[key]=value
    return {'schema_version':'editorial-features-v1','values':values,
            'missing':{key:value is None for key,value in values.items()},
            'origins':{key:'source' if key in FEATURES[:3] else 'versioned_signal' for key in FEATURES},
            'versions':{key:str(value) for key,value in versions.items() if key in ('schema','snapshot_id')}}
