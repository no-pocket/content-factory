"""One-source narrative assembly with a frame-count clock and word provenance."""
from __future__ import annotations

import copy
from fractions import Fraction
import math
import re
import subprocess
import json
from pathlib import Path

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
        keys = {'segment_id', 'source_in', 'source_out', 'output_start', 'purpose', 'framing', 'framing_resolved', 'frame_count', 'duration'}
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
            from .framing import validate_scene, validate_framing
            clean['framing'] = validate_scene(clean['framing'])
            if clean.get('framing_resolved'):
                resolved = clean['framing_resolved']
                if resolved != validate_framing(clean['framing'], tuple(resolved['source_size']), (720,1280)):
                    raise ValueError('Invalid segment framing geometry')
        elif 'framing_resolved' in clean:
            raise ValueError('Resolved framing without source scene')
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
        selected = any((start < s['source_out'] and end > s['source_in']) or
                       (start == end and s['source_in'] <= start < s['source_out']) for s in plan['segments'])
        if not selected:
            continue
        if not 0 <= start < end <= plan['source_duration']:
            raise ValueError('Invalid source word timing')
        text = word.get('text', word.get('word', ''))
        if not isinstance(text, str) or not text.strip() or len(text) > 64:
            raise ValueError('Invalid source word text')
        for segment in plan['segments']:
            if start < segment['source_out'] and end > segment['source_in']:
                if start < segment['source_in']-1e-7 or end > segment['source_out']+1e-7:
                    raise ValueError('Assembly cuts a partial source word')
                mapped.append({'start': segment['output_start']+start-segment['source_in'],
                               'end': segment['output_start']+end-segment['source_in'], 'text': text.strip(),
                               'word_id': word.get('word_id', str(index)), 'segment_id': segment['segment_id'],
                               'output_segment_end': segment['output_start']+segment['duration'],
                               'source_start': start, 'source_end': end})
    return sorted(mapped, key=lambda w:(w['start'],w['end']))


def build_assembly_context(plan: dict, segments: list[dict]) -> dict:
    plan = validate_assembly(plan, plan['source_duration'])
    source_words = [{**word,'word_id':f'{i}:{j}'} for i,s in enumerate(segments) for j,word in enumerate(s.get('words',[]))]
    words = map_words(plan, source_words)
    excluded_zero = [w['word_id'] for w in source_words if w['start']==w['end']]
    anchored = []
    for interval in plan['segments']:
        for index, segment in enumerate(segments):
            if segment['start'] < interval['source_out'] and segment['end'] > interval['source_in']:
                selected = [w for w in words if w['segment_id']==interval['segment_id'] and
                            w['source_start'] >= segment['start'] and w['source_end'] <= segment['end']]
                anchored.append({'segment_id': index, 'source_start':max(segment['start'],interval['source_in']),
                                 'source_end':min(segment['end'],interval['source_out']),
                                 'text':' '.join(w['text'] for w in selected) if selected else segment.get('text',''),
                                 'words':selected})
    return {'schema_version':'1.0','text':' '.join(w['text'] for w in words) if words else ' '.join(s['text'] for s in anchored),
            'segments':anchored,'before':[],'after':[], 'assembly':plan,
            'word_timing_diagnostics':{'excluded_zero_duration_words_outside_assembly':excluded_zero,
                                       'selected_words_have_positive_duration':True},
            'source_range':{'start':min(s['source_in'] for s in plan['segments']),'end':max(s['source_out'] for s in plan['segments'])},
            'coverage':{'complete_candidate':True,'prefix_truncated':False,'discontinuous':True}}


def render_assembly(source: Path, plan: dict, target: Path, *, quality: str = 'standard', framing: dict | None = None) -> dict:
    """Concatenate decoded source intervals, keeping A/V on the same frame clock."""
    plan = validate_assembly(plan, plan['source_duration'])  # no subprocess for invalid plans
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
    actual_duration = float(probe['format']['duration'])
    if abs(actual_duration-plan['source_duration']) > 1/FPS:
        raise ValueError('Assembly duration differs from actual source')
    audio = any(s['codec_type']=='audio' for s in probe['streams'])
    video = next(s for s in probe['streams'] if s['codec_type']=='video')
    filters, labels = [], []
    from .framing import validate_framing, video_filter
    for index, segment in enumerate(plan['segments']):
        scene = segment.get('framing')
        resolved = validate_framing(scene,(video['width'],video['height']),(720,1280)) if scene else framing
        if scene:
            segment['framing_resolved'] = resolved
        vf = video_filter(resolved,720,1280) if resolved else 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280'
        start, end, duration = segment['source_in'], segment['source_out'], segment['duration']
        filters.append(f'[0:v:0]trim=start={start}:end={end},setpts=PTS-STARTPTS,fps=30,tpad=stop_mode=clone:stop_duration={duration},trim=end_frame={segment["frame_count"]},{vf},setsar=1[v{index}]')
        labels.append(f'[v{index}]')
        if audio:
            filters.append(f'[0:a:0]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=48000,apad,atrim=duration={duration}[a{index}]')
            labels.append(f'[a{index}]')
    filters.append(''.join(labels)+f'concat=n={len(plan["segments"])}:v=1:a={int(audio)}[video]'+('[audio]' if audio else ''))
    target.parent.mkdir(parents=True,exist_ok=True)
    args=['ffmpeg','-nostdin','-v','error','-y','-i',str(source),'-filter_complex',';'.join(filters),'-map','[video]']
    if audio:
        args += ['-map','[audio]','-c:a','aac','-b:a','160k']
    args += ['-c:v','libx264','-preset','veryfast','-crf','16' if quality=='high' else '24','-pix_fmt','yuv420p','-r','30',
             '-t',str(plan['duration']),'-movflags','+faststart',str(target)]
    subprocess.run(args,check=True,capture_output=True,text=True,timeout=900)
    return plan
