"""Deterministic framing with explicit normalized ROI; no vision dependencies."""
from __future__ import annotations

import math
import re

PRESETS = ('face', 'gameplay', 'web', 'tweet', 'document')


def validate_scene(scene: dict) -> dict:
    if not isinstance(scene, dict) or set(scene)-{'preset', 'roi', 'layout_version'}:
        raise ValueError('Invalid framing fields')
    if not scene:
        return {}
    if scene.get('preset') not in PRESETS:
        raise ValueError('Invalid framing preset')
    if scene.get('layout_version') not in (None,'fit_v1','proof_compact_v2'):
        raise ValueError('Unsupported framing layout version')
    roi = scene.get('roi')
    if roi is None:
        roi = ({'x': .4, 'y': .2, 'width': .2, 'height': .4} if scene['preset'] == 'face' else
               {'x': 0, 'y': 0, 'width': 1, 'height': 1})
    if not isinstance(roi, dict) or set(roi) != {'x', 'y', 'width', 'height'}:
        raise ValueError('ROI requires normalized x, y, width, height')
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in roi.values()):
        raise ValueError('Invalid ROI coordinates')
    x, y, w, h = (roi[k] for k in ('x', 'y', 'width', 'height'))
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1 and x+w <= 1+1e-9 and y+h <= 1+1e-9):
        raise ValueError('ROI outside source or empty')
    return {'preset': scene['preset'], 'roi': dict(roi), **({'layout_version':scene['layout_version']} if 'layout_version' in scene else {})}


def _overlap(a, b):
    return (max(a['x'], b['x']) < min(a['x']+a['width'], b['x']+b['width']) and
            max(a['y'], b['y']) < min(a['y']+a['height'], b['y']+b['height']))


def validate_framing(scene: dict, source_size: tuple[int, int], output_size: tuple[int, int]) -> dict:
    scene = validate_scene(scene)
    if not scene:
        return {}
    if any(type(v) is not int or v <= 0 for v in (*source_size, *output_size)) or len(source_size) != 2 or len(output_size) != 2:
        raise ValueError('Invalid frame dimensions')
    sw, sh = source_size
    ow, oh = output_size
    roi = scene['roi']
    if scene.get('layout_version')=='proof_compact_v2':
        x=max(0,math.floor(roi['x']*sw/2)*2);y=max(0,math.floor(roi['y']*sh/2)*2)
        right=min(sw,math.ceil((roi['x']+roi['width'])*sw/2)*2)
        bottom=min(sh,math.ceil((roi['y']+roi['height'])*sh/2)*2)
        cw,ch=right-x,bottom-y
        if min(cw,ch)<2:raise ValueError('ROI is smaller than a source pixel region')
        scale=min(ow/cw,oh*.60/ch)
        width=max(2,math.floor(cw*scale/2)*2);height=max(2,math.floor(ch*scale/2)*2)
        left=math.floor((ow-width)/4)*2;top=math.floor((oh*.47-height/2)/2)*2
        image={'x':left/ow,'y':top/oh,'width':width/ow,'height':height/oh}
        captions={'x':.05,'y':(top+height+math.ceil(oh*.025))/oh,'width':.9,'height':.12}
        title={'x':.08,'y':max(oh*.02,top-oh*.14-oh*.025)/oh,'width':.84,'height':.14}
        return {**scene,'mode':'contain','focus':{'x':roi['x']+roi['width']/2,'y':roi['y']+roi['height']/2},
                'roi_visible':True,'projected_roi':image,'caption_safe_area':captions,'title_safe_area':title,
                'content_box':image,'image_box':image,'crop_pixels':{'x':x,'y':y,'width':cw,'height':ch},
                'background':'source_blur','source_size':list(source_size),'output_size':list(output_size)}
    mode = 'contain' if scene['preset'] in ('web', 'tweet', 'document') else 'cover'
    cx, cy = roi['x']+roi['width']/2, roi['y']+roi['height']/2
    scale = max(ow/sw, oh/sh)
    crop_x = min(max(sw*scale*cx-ow/2, 0), sw*scale-ow)
    crop_y = min(max(sh*scale*cy-oh/2, 0), sh*scale-oh)
    projected = {'x': (roi['x']*sw*scale-crop_x)/ow, 'y': (roi['y']*sh*scale-crop_y)/oh,
                 'width': roi['width']*sw*scale/ow, 'height': roi['height']*sh*scale/oh}
    if any(projected[k] < -1e-6 for k in ('x', 'y')) or projected['x']+projected['width'] > 1+1e-6 or projected['y']+projected['height'] > 1+1e-6:
        mode = 'contain'
    captions = {'x': .05, 'y': .84, 'width': .9, 'height': .12}
    content_box = {'x': 0, 'y': 0, 'width': 1, 'height': 1}
    if mode == 'cover' and _overlap(projected, captions):
        top = {**captions, 'y': .06}
        if _overlap(projected, top):
            mode = 'contain'
        else:
            captions = top
    if mode == 'contain':
        content_box = {'x': 0, 'y': .05, 'width': 1, 'height': .60}
        scale = min(ow/sw, oh*.60/sh)
        x = (ow-sw*scale)/2
        y = oh*.05+(oh*.60-sh*scale)/2
        projected = {'x': (x+roi['x']*sw*scale)/ow, 'y': (y+roi['y']*sh*scale)/oh,
                     'width': roi['width']*sw*scale/ow, 'height': roi['height']*sh*scale/oh}
    if _overlap(projected, captions):
        raise ValueError('No caption-safe area preserves the important source region')
    return {**scene, 'mode': mode, 'focus': {'x': cx, 'y': cy}, 'roi_visible': True,
            'projected_roi': projected, 'caption_safe_area': captions, 'content_box': content_box,
            'title_safe_area': {'x': .08, 'y': .67 if mode == 'contain' else .02, 'width': .84, 'height': .15},
            'source_size': list(source_size), 'output_size': list(output_size)}


def video_filter(framing: dict, width: int, height: int) -> str:
    if framing.get('layout_version')=='proof_compact_v2':
        crop=framing['crop_pixels'];box=framing['image_box']
        w,h=round(box['width']*width),round(box['height']*height)
        x,y=round(box['x']*width),round(box['y']*height)
        return f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']},scale={w}:{h},pad={width}:{height}:{x}:{y}:color=0x0c101a"
    if framing['mode'] == 'contain':
        panel_height = int(height*framing['content_box']['height'])//2*2
        panel_y = round(height*framing['content_box']['y'])
        return (f'scale={width}:{panel_height}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                f'pad={width}:{height}:(ow-iw)/2:{panel_y}+({panel_height}-ih)/2:color=0x0c101a')
    cx, cy = framing['focus']['x'], framing['focus']['y']
    return (f'scale={width}:{height}:force_original_aspect_ratio=increase,'
            f"crop={width}:{height}:'min(max(iw*{cx}-ow/2,0),iw-ow)':'min(max(ih*{cy}-oh/2,0),ih-oh)'")


def normalize_source_windows(value, source_duration: float | None=None) -> list[dict]:
    if value is None or value=='':return []
    if isinstance(value,str):
        if len(value)>2000:raise ValueError('Too many framing intervals')
        parsed=[]
        for part in value.split(';'):
            match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*',part)
            if not match:raise ValueError('Use source intervals such as 12.5-18; 40-47.2')
            parsed.append({'start':float(match[1]),'end':float(match[2])})
        value=parsed
    if not isinstance(value,list) or len(value)>24:raise ValueError('Framing intervals must be a list of at most 24')
    clean=[]
    for item in value:
        if not isinstance(item,dict) or set(item)!={'start','end'}:raise ValueError('Invalid framing interval fields')
        a,b=item['start'],item['end']
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in (a,b)) or not 0<=a<b:
            raise ValueError('Invalid framing interval')
        if source_duration is not None and b>source_duration+1e-7:raise ValueError('Framing interval outside source duration')
        clean.append({'start':a,'end':b})
    clean.sort(key=lambda item:item['start'])
    if any(a['end']>b['start'] for a,b in zip(clean,clean[1:])):raise ValueError('Framing intervals overlap')
    return clean


def build_framing_schedule(clip: dict, settings: dict) -> list[dict]:
    windows=normalize_source_windows(settings.get('framing_windows',[]))
    scene=validate_scene({'preset':settings['framing_preset'],'roi':settings.get('framing_roi'),'layout_version':'proof_compact_v2'})
    pieces=clip.get('assembly',{}).get('segments') or [{'source_in':clip['start'],'source_out':clip['end'],'output_start':0}]
    result=[]
    for piece in pieces:
        for window in windows:
            a,b=max(piece['source_in'],window['start']),min(piece['source_out'],window['end'])
            if a<b:
                result.append({'start':piece['output_start']+a-piece['source_in'],
                               'end':piece['output_start']+b-piece['source_in'],'framing':scene})
    return sorted(result,key=lambda item:item['start'])


def validate_framing_schedule(schedule: list, duration: float, source_size=None) -> list[dict]:
    if type(duration) not in (float,int) or not math.isfinite(duration) or duration<=0:
        raise ValueError('Invalid framing schedule duration')
    if not isinstance(schedule,list) or len(schedule)>8:raise ValueError('At most 8 proof intervals per candidate')
    clean=[]
    for item in schedule:
        if not isinstance(item,dict) or set(item)-{'start','end','framing','framing_resolved'} or not {'start','end','framing'}<=set(item):
            raise ValueError('Invalid framing schedule fields')
        a,b=item['start'],item['end']
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in (a,b)) or not 0<=a<b<=duration+1e-7:
            raise ValueError('Invalid framing schedule bounds')
        scene=validate_scene(item['framing']);result={**item,'framing':scene}
        if source_size is not None:
            result['framing_resolved']=validate_framing(scene,source_size,(720,1280))
        elif item.get('framing_resolved'):
            resolved=item['framing_resolved']
            if resolved!=validate_framing(scene,tuple(resolved['source_size']),(720,1280)):
                raise ValueError('Invalid framing schedule geometry')
        if clean and a<clean[-1]['end']-1e-7:raise ValueError('Framing schedule overlaps or is out of order')
        clean.append(result)
    return clean


def framing_graph(input_label: str, output_label: str, *, framing=None, schedule=(), width=720, height=1280) -> str:
    """Build backend-owned filter branches; windows change pixels, never the clock."""
    def scene_graph(source,dest,scene):
        if scene and scene.get('layout_version')=='proof_compact_v2':
            crop=scene['crop_pixels'];box=scene['image_box']
            w,h=round(box['width']*width),round(box['height']*height)
            x,y=round(box['x']*width),round(box['y']*height)
            return [f'[{source}]split=2[{dest}_bgin][{dest}_fgin]',
                    f'[{dest}_bgin]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:2,colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[{dest}_bg]',
                    f"[{dest}_fgin]crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']},scale={w}:{h},setsar=1[{dest}_fg]",
                    f'[{dest}_bg][{dest}_fg]overlay={x}:{y}:shortest=1,setsar=1[{dest}]']
        vf=video_filter(scene,width,height) if scene else f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}'
        return [f'[{source}]{vf},setsar=1[{dest}]']
    if not schedule:return ';'.join(scene_graph(input_label,output_label,framing))
    labels=[output_label+'_normalin']+[f'{output_label}_proofin{i}' for i in range(len(schedule))]
    graph=[f'[{input_label}]split={len(labels)}'+''.join(f'[{label}]' for label in labels)]
    graph+=scene_graph(labels[0],output_label+'_base0',framing)
    for i,window in enumerate(schedule):
        scene=window['framing_resolved'];proof=f'{output_label}_proof{i}'
        graph+=scene_graph(labels[i+1],proof,scene)
        dest=output_label if i==len(schedule)-1 else f'{output_label}_base{i+1}'
        graph.append(f"[{output_label}_base{i}][{proof}]overlay=0:0:enable='gte(t,{window['start']})*lt(t,{window['end']})':shortest=1[{dest}]")
    return ';'.join(graph)
