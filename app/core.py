"""Deterministic clip selection and local FFmpeg renderer. No remote downloads."""
from __future__ import annotations
import json
import math
import re
import subprocess
import logging
import textwrap
from pathlib import Path

HOOK_WORDS = ("gta", "rockstar", "vice city", "lucia", "jason", "incrível", "segredo", "revel", "surpresa", "importante", "descob", "never", "wow", "crazy", "secret", "insane", "actually", "first", "new")


def propose_clips(segments: list[dict], duration: float, *, count: int = 3, target: int = 40, min_seconds: int = 15, max_seconds: int = 60) -> list[dict]:
    """Select distinct speech-filled windows. This is a heuristic, NOT an LLM quality score."""
    if duration <= 0:
        return []
    clean = sorted((s for s in segments if float(s.get("end", 0)) > float(s.get("start", 0))), key=lambda s: s["start"])
    if not clean:
        return []
    candidates = []
    for idx, seg in enumerate(clean):
        start = float(seg["start"])
        # Join successive ASR segments until target length (max 60s).
        group = []
        for nxt in clean[idx:]:
            if float(nxt["end"]) - start > max_seconds:
                break
            if group and float(nxt["start"]) - float(group[-1]["end"]) > 7:
                break
            group.append(nxt)
            if float(nxt["end"]) - start >= target:
                break
        if not group:
            continue
        end = min(duration, float(group[-1]["end"]))
        length = end - start
        if length < min_seconds:
            continue
        content = " ".join(str(x.get("text", "")) for x in group).strip()
        if not content:
            continue
        hits = sum(content.lower().count(w) for w in HOOK_WORDS)
        word_count = len(content.split())
        density = word_count / max(length, 1)
        score = round(hits * 2 + min(density, 3) + (2 if 28 <= length <= 52 else 0), 2)
        candidates.append({"start": round(start, 2), "end": round(end, 2), "score": score,
                           "text": content, "reason": f"{hits} palavras-chave; {word_count} palavras; {length:.0f}s"})
    chosen = []
    for c in sorted(candidates, key=lambda x: (-x["score"], x["start"])):
        if all(max(0, min(c["end"], x["end"]) - max(c["start"], x["start"])) < 0.20 * min(c["end"]-c["start"], x["end"]-x["start"]) for x in chosen):
            chosen.append(c)
            if len(chosen) == count:
                break
    return sorted(chosen, key=lambda x: x["start"])


def srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hh, ms = divmod(ms, 3600000)
    mm, ms = divmod(ms, 60000)
    ss, ms = divmod(ms, 1000)
    return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"


def write_srt(segments: list[dict], clip_start: float, clip_end: float, path: Path) -> None:
    """Short cues from actual word timing; segment-only fallback is explicitly approximate."""
    from .timeline import normalized_words
    words = normalized_words(segments, clip_start, clip_end)
    cues = []
    if words:
        group = []
        for word in words:
            if group and (len(group) >= 3 or word['start'] - group[-1]['end'] > .6 or
                          word['end'] - group[0]['start'] > 1.6 or
                          sum(len(w['text'])+1 for w in group) + len(word['text']) > 40):
                cues.append((group[0]['start'], group[-1]['end'], ' '.join(w['text'] for w in group)))
                group = []
            group.append(word)
        if group:
            cues.append((group[0]['start'], group[-1]['end'], ' '.join(w['text'] for w in group)))
    else:
        logging.getLogger(__name__).warning('Word timestamps unavailable: FFmpeg phrase timing is estimated from segments')
        for segment in segments:
            start, end = max(clip_start, float(segment['start'])), min(clip_end, float(segment['end']))
            tokens = str(segment.get('text', '')).split()
            if end <= start or not tokens:
                continue
            for offset in range(0, len(tokens), 3):
                stop = min(offset+3, len(tokens))
                cues.append((start-clip_start+(end-start)*offset/len(tokens),
                             start-clip_start+(end-start)*stop/len(tokens), ' '.join(tokens[offset:stop])))
    lines = []
    for ordinal, (start, end, text) in enumerate(cues, 1):
        caption = '\n'.join(textwrap.wrap(re.sub(r'[\r\n]+', ' ', text), width=32))
        lines.extend([str(ordinal), f'{srt_time(start)} --> {srt_time(end)}', caption, ''])
    path.write_text('\n'.join(lines), encoding='utf-8')


def get_duration(source: Path) -> float:
    cp = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(source)], capture_output=True, text=True, check=True)
    return float(cp.stdout.strip())


def render(source: Path, start: float, end: float, segments: list[dict], target: Path, *, width: int = 720, height: int = 1280, burn_subtitles: bool = True, crf: int = 24, framing: dict | None = None) -> None:
    """Center-crop landscape to 9:16. Produces a preview, not automatic face tracking."""
    if start < 0 or end <= start or end - start > 60.01:
        raise ValueError("Interval must be between 0 and 60 seconds")
    target.parent.mkdir(parents=True, exist_ok=True)
    subtitle = target.with_suffix(".srt")
    write_srt(segments, start, end, subtitle)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"
    if framing:
        from .framing import video_filter
        vf = video_filter(framing, width, height)+',setsar=1'
    # Use the local SRT filename relative to CWD to avoid FFmpeg filter path escaping.
    if burn_subtitles and subtitle.stat().st_size > 0:
        vf += ",subtitles=" + subtitle.name + ":force_style='FontName=DejaVu Sans,FontSize=15,Outline=2,Shadow=1,Alignment=2,MarginV=55'"
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-i", str(source), "-t", str(end-start), "-vf", vf,
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(target)]
    subprocess.run(args, check=True, cwd=str(target.parent), capture_output=True, text=True)


def atomic_json(path: Path, value: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
