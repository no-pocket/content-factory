"""Append a ready, licensed owner clip; never synthesize speech or fetch media."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import uuid


def append_outro(target: Path, asset_id: str, assets: dict, *, quality='standard', expected_sha256=None) -> dict:
    from .timeline import ASSET_ID
    from .core import get_duration
    from .quality import expects_audio
    from .edit_render import ASSETS_ROOT
    if not isinstance(asset_id, str) or not ASSET_ID.fullmatch(asset_id) or asset_id not in assets:
        raise ValueError('Outro must be a registered licensed asset')
    asset = assets[asset_id]
    source = Path(asset['path']).resolve()
    if not source.is_relative_to(ASSETS_ROOT.resolve()) or not source.is_file() or not asset.get('license_note'):
        raise ValueError('Invalid licensed outro path')
    with source.open('rb') as stream:
        fingerprint = hashlib.file_digest(stream, 'sha256').hexdigest()
    if expected_sha256 is not None and fingerprint != expected_sha256:
        raise ValueError('Licensed outro bytes changed since prior render')
    duration = get_duration(source)
    if not math.isfinite(duration) or not 2 <= duration <= 120:
        raise ValueError('Outro must be between 2 and 120 seconds')
    size = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(target)]))['streams'][0]
    width, height = size['width'], size['height']
    base_duration = get_duration(target)
    args = ['ffmpeg','-nostdin','-v','error','-y','-i',str(target),'-i',str(source)]
    filters = []
    for i, (path, length) in enumerate(((target,base_duration),(source,duration))):
        filters.append(f'[{i}:v:0]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}]')
        if expects_audio(path):
            filters.append(f'[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={length},asetpts=PTS-STARTPTS[a{i}]')
        else:
            filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={length},asetpts=PTS-STARTPTS[a{i}]')
    filters.append('[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]')
    pending=target.with_name(f'{target.stem}.outro.{uuid.uuid4().hex}.mp4')
    try:
        subprocess.run(args+['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]',
            '-c:v','libx264','-preset','veryfast','-crf','18' if quality=='high' else '24',
            '-c:a','aac','-b:a','160k','-movflags','+faststart',str(pending)],check=True,capture_output=True,text=True)
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(pending),'-f','null','-'],check=True,capture_output=True,text=True)
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != fingerprint:
                raise ValueError('Licensed outro changed while rendering')
        os.replace(pending,target)
        return {'asset_id':asset_id,'sha256':fingerprint,'start':base_duration,'duration':duration,
                'output_duration':get_duration(target),'license_note':asset['license_note']}
    finally:
        pending.unlink(missing_ok=True)
