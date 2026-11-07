"""Versioned, bounded edit decision list (EDL). No arbitrary model supplied paths/commands.

The producer of this JSON may be a local LLM, but only deterministic, validated
commands are permitted to reach FFmpeg/Remotion. Times are relative to the clip.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

FPS = 30
MAX_CLIP_SECONDS = 60
ASSET_ID = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


def as_float(value, fallback=0.0):
    try:
        num = float(value)
        if num != num or num in (float("inf"), -float("inf")):
            return fallback
        return num
    except (ValueError, TypeError):
        return fallback


def normalized_words(segments: list[dict], start: float, end: float) -> list[dict]:
    """Use ASR word timing as source of truth; no fabricated timings when missing."""
    output = []
    for segment in segments:
        for word in segment.get("words", []):
            a = max(start, as_float(word.get("start"), -1))
            b = min(end, as_float(word.get("end"), -1))
            token = str(word.get("text", word.get("word", ""))).strip()
            if b <= a or not token:
                continue
            if token.lower().strip(".,!?;:") in ("lúcia", "lucia"):
                token = "Lucia" + (token[-1] if token[-1] in ".,!?:;" else "")
            elif token.lower().strip(".,!?;:") == "rockstar":
                token = "Rockstar" + (token[-1] if token[-1] in ".,!?:;" else "")
            output.append({"start": round(a-start, 3), "end": round(b-start, 3), "text": token[:64]})
    return sorted(output, key=lambda w: (w["start"], w["end"]))


def build_timeline(clip: dict, segments: list[dict], *, edit: dict | None = None, assets: dict | None = None,
                   editorial_title: str | None = None) -> dict:
    """Build validated timeline from ASR + constrained director hints."""
    start = as_float(clip["start"])
    end = as_float(clip["end"])
    duration = round(end - start, 3)
    if not (0 < duration <= MAX_CLIP_SECONDS):
        raise ValueError("Clip duration must be within 0..60 seconds")
    words = normalized_words(segments, start, end)
    edit = edit if isinstance(edit, dict) else {}
    assets = assets or {}
    text = str(clip.get("text", ""))
    from .editorial_context import validate_title
    title_check = validate_title(edit.get('hook', ''), {'text': text})
    hook = title_check['normalized'] if title_check['valid'] else ''
    if editorial_title is not None:
        if (not isinstance(editorial_title, str) or not 1 <= len(editorial_title.strip()) <= 80
                or len(editorial_title.split()) > 12 or not any(c.isalpha() for c in editorial_title)
                or any(ord(c) < 32 for c in editorial_title)):
            raise ValueError('Editorial title must contain 1..80 characters and at most 12 words')
        hook = editorial_title.strip()

    fx = []
    for effect in edit.get("effects", []) if isinstance(edit.get("effects"), list) else []:
        if not isinstance(effect, dict) or effect.get("type") != "punch_zoom":
            continue
        t = as_float(effect.get("at"), -1)
        if 0.3 <= t <= duration-0.5 and all(abs(t - old["at"]) >= 3 for old in fx):
            fx.append({"type": "punch_zoom", "at": round(t, 3), "duration": 0.38})
        if len(fx) >= 3:
            break

    broll = []
    for piece in edit.get("broll", []) if isinstance(edit.get("broll"), list) else []:
        if not isinstance(piece, dict):
            continue
        ident = str(piece.get("asset_id", ""))
        if not ASSET_ID.fullmatch(ident) or ident not in assets:
            continue
        at = as_float(piece.get("at"), -1)
        length = max(0, min(5, as_float(piece.get("duration"), 3)))
        available_length = as_float(assets[ident].get("duration"), 0)
        source_start = max(0, as_float(piece.get("source_start", 0)))
        if at < 1 or at + length > duration-1 or length < 1.5 or source_start+length > available_length:
            continue
        if any(max(at, other["at"]) < min(at+length, other["at"]+other["duration"]) for other in broll):
            continue
        broll.append({"asset_id": ident, "at": round(at, 3), "duration": round(length, 3), "source_start": round(source_start, 3)})
        if len(broll) >= 2:
            break

    timeline = {
        "schema_version": "2.0", "width": 720, "height": 1280, "fps": FPS,
        "duration": duration, "source_range": {"start": start, "end": end},
        "layers": {
            "video": {"path": "base.mp4", "start": 0, "duration": duration},
            "audio": {"from": "base.mp4", "start": 0, "duration": duration},
            "captions": words,
            "text": [{"text": hook, "at": 0.5, "duration": min(2.5, max(0.6, duration - 0.6)), "animation": "pop",
                      "style": "compact_editorial_v1", "origin": "human" if editorial_title is not None else "model"}] if hook else [],
            "effects": fx, "broll": broll,
        },
        "caption_style": "bold_karaoke_v1",
        "finishing": {"tail_seconds": 0.35, "fade_seconds": 0.25},
    }
    validate_timeline(timeline)
    return timeline


def output_duration(timeline: dict) -> float:
    """Legacy timelines have no tail; source range and caption timings remain unchanged."""
    return round(timeline['duration'] + timeline.get('finishing', {}).get('tail_seconds', 0), 3)


def candidate_duration(clip: dict) -> float:
    return output_duration({'duration': clip['end'] - clip['start'], **(clip.get('timeline') or {})})


def validate_timeline(timeline: dict) -> None:
    if timeline.get("schema_version") != "2.0" or timeline.get("fps") != FPS or timeline.get("width") != 720 or timeline.get("height") != 1280:
        raise ValueError("Unsupported timeline schema or output settings")
    duration = as_float(timeline.get("duration"))
    if not 0 < duration <= MAX_CLIP_SECONDS:
        raise ValueError("Invalid timeline duration")
    if 'finishing' in timeline:
        finishing = timeline['finishing']
        if not isinstance(finishing, dict) or set(finishing) != {'tail_seconds', 'fade_seconds'}:
            raise ValueError('Invalid finishing settings')
        tail, fade = finishing['tail_seconds'], finishing['fade_seconds']
        if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (tail, fade))
                or not 0 < fade <= tail <= 0.75):
            raise ValueError('Invalid finishing duration')
    layers = timeline.get("layers")
    if not isinstance(layers, dict) or layers.get("video", {}).get("path") != "base.mp4":
        raise ValueError("Timeline can only reference staged base.mp4")
    for key in ("captions", "text", "effects", "broll"):
        if not isinstance(layers.get(key), list):
            raise ValueError(f"Missing {key} layer")
    for word in layers["captions"]:
        if not 0 <= as_float(word.get("start"), -1) < as_float(word.get("end"), -1) <= duration + 0.002:
            raise ValueError("Invalid subtitle timings")
    for item in layers["broll"]:
        if not ASSET_ID.fullmatch(item.get("asset_id", "")) or not 0 <= item["at"] < item["at"]+item["duration"] <= duration:
            raise ValueError("Invalid B-roll event")


def write_timeline(path: Path, timeline: dict) -> None:
    validate_timeline(timeline)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
