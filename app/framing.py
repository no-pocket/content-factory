"""Deterministic framing with explicit normalized ROI; no vision dependencies."""
from __future__ import annotations

import math

PRESETS = ('face', 'gameplay', 'web', 'tweet', 'document')


def validate_scene(scene: dict) -> dict:
    if not isinstance(scene, dict) or set(scene)-{'preset', 'roi'}:
        raise ValueError('Invalid framing fields')
    if not scene:
        return {}
    if scene.get('preset') not in PRESETS:
        raise ValueError('Invalid framing preset')
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
    return {'preset': scene['preset'], 'roi': dict(roi)}


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
    if framing['mode'] == 'contain':
        panel_height = int(height*framing['content_box']['height'])//2*2
        panel_y = round(height*framing['content_box']['y'])
        return (f'scale={width}:{panel_height}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                f'pad={width}:{height}:(ow-iw)/2:{panel_y}+({panel_height}-ih)/2:color=0x0c101a')
    cx, cy = framing['focus']['x'], framing['focus']['y']
    return (f'scale={width}:{height}:force_original_aspect_ratio=increase,'
            f"crop={width}:{height}:'min(max(iw*{cx}-ow/2,0),iw-ow)':'min(max(ih*{cy}-oh/2,0),ih-oh)'")
