"""Advisory readability measurements for the captions actually rendered."""
from __future__ import annotations
import math

def analyze_caption_readability(timeline, *, max_cps=20, max_chars=84):
    if not math.isfinite(max_cps) or not 1<=max_cps<=100 or type(max_chars) is not int or not 1<=max_chars<=500:
        raise ValueError('Invalid caption limits')
    captions=timeline.get('layers',{}).get('captions',[])
    groups=[]
    for word in captions:
        if timeline.get('caption_style')=='phrase_v1': groups.append([word]); continue
        if not groups or len(groups[-1])>=3 or word['start']-groups[-1][-1]['end']>.6 or word['end']-groups[-1][0]['start']>1.6 or word.get('segment_id')!=groups[-1][0].get('segment_id'):
            groups.append([])
        groups[-1].append(word)
    warnings=[]
    for group in groups:
        start,end=group[0]['start'],group[-1]['end']; text=' '.join(str(w.get('text','')).strip() for w in group).strip()
        duration=end-start
        if duration<=0: warnings.append({'code':'caption_invalid_duration','start':start,'end':end}); continue
        cps=round(len(text)/duration,1)
        if cps>max_cps: warnings.append({'code':'caption_fast','start':start,'end':end,'characters_per_second':cps,'limit':max_cps})
        if len(text)>max_chars: warnings.append({'code':'caption_long','start':start,'end':end,'characters':len(text),'limit':max_chars})
    return {'version':1,'limits':{'max_cps':max_cps,'max_chars':max_chars},'warnings':warnings}
