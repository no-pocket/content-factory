"""Read attachment geometry from the encoded master, never a client default."""
from __future__ import annotations
import json
import math
import subprocess
from pathlib import Path


def get_delivery_metadata(path: Path) -> dict:
    """Return Telegram sendVideo parameters for a square-pixel H.264 master.

    A master must already have passed the normal complete-decoding QC gate.
    Nontrivial SAR/rotation needs normalization as a new render, not metadata lies.
    """
    result = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format',
                             '-of','json',str(path)],check=True,capture_output=True,text=True)
    try:
        info = json.loads(result.stdout)
        videos = [s for s in info['streams'] if s.get('codec_type') == 'video']
        if len(videos) != 1:
            raise ValueError('Expected exactly one video stream')
        stream = videos[0]
        width, height = stream['width'], stream['height']
        duration = float(info['format']['duration'])
        if stream.get('codec_name') != 'h264' or stream.get('sample_aspect_ratio', '1:1') != '1:1':
            raise ValueError('Delivery requires square-pixel H.264')
        rotations = [stream.get('tags', {}).get('rotate', 0)]
        rotations += [side.get('rotation', 0) for side in stream.get('side_data_list', [])]
        if any(float(r) % 360 for r in rotations):
            raise ValueError('Delivery requires unrotated pixels')
        if (type(width) is not int or type(height) is not int or not 0 < width <= 8192
                or not 0 < height <= 8192 or not math.isfinite(duration) or duration <= 0):
            raise ValueError('Invalid delivery geometry or duration')
        if any(s.get('codec_type') == 'audio' and s.get('codec_name') != 'aac' for s in info['streams']):
            raise ValueError('Delivery requires AAC audio')
    except (KeyError, TypeError, OverflowError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid media probe for delivery') from exc
    # Existing render/QC produces +faststart MP4; only advertise streaming when
    # its atom ordering proves the index precedes the media payload.
    return {'width':width,'height':height,'duration':math.ceil(duration),
            'supports_streaming':_faststart(path)}


def _faststart(path: Path) -> bool:
    size = path.stat().st_size
    with path.open('rb') as stream:
        position = 0
        while position + 8 <= size:
            header = stream.read(8)
            length, kind = int.from_bytes(header[:4], 'big'), header[4:]
            header_size = 8
            if length == 1:
                extended = stream.read(8)
                if len(extended) != 8:
                    return False
                length, header_size = int.from_bytes(extended, 'big'), 16
            if length < header_size or position + length > size:
                return False
            if kind == b'moov':
                return True
            if kind == b'mdat':
                return False
            position += length
            stream.seek(position)
    return False
