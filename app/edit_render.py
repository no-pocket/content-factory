"""FFmpeg stages media, Remotion composes animated layers. No model-supplied paths.

The exact timeline is stored next to each candidate for reproducibility.
"""
from __future__ import annotations
import json
import os
import subprocess
import logging
import logging
from pathlib import Path

from .core import render
from .timeline import ASSET_ID, validate_timeline, write_timeline

log = logging.getLogger(__name__)

log = logging.getLogger(__name__)

ASSETS_ROOT = Path(os.getenv("ASSETS_DIR", "/data/assets"))
PUBLIC = Path(os.getenv("RENDER_PUBLIC_DIR", "/app/renderer/public/jobs"))
RENDERER = Path(os.getenv("REMOTION_DIR", "/app/renderer"))


def read_assets() -> dict:
    """Register only assets with explicit documented rights and safe local paths."""
    catalog = ASSETS_ROOT / "catalog.json"
    if not catalog.exists():
        return {}
    data = json.loads(catalog.read_text(encoding="utf-8"))
    result = {}
    for record in data.get("assets", []):
        if not isinstance(record, dict):
            continue
        ident = str(record.get("asset_id", ""))
        if not ASSET_ID.fullmatch(ident) or not record.get("license_note"):
            continue
        rel = Path(str(record.get("file", "")))
        full = (ASSETS_ROOT / rel).resolve()
        if rel.is_absolute() or not full.is_relative_to(ASSETS_ROOT.resolve()) or not full.is_file():
            continue
        try:
            duration = float(record.get("duration", 0))
        except (ValueError, TypeError):
            continue
        if not 2 <= duration <= 7200:
            continue
        result[ident] = {"path": full, "duration": duration, "description": str(record.get("description", ""))[:150], "license_note": record["license_note"]}
    return result


def render_edited(source: Path, job_id: str, ordinal: int, clip: dict, segments: list[dict], timeline: dict, assets: dict, target: Path) -> str:
    """Use FFmpeg for normalization and Remotion for visual edits, fallback if configured."""
    validate_timeline(timeline)
    output_dir = PUBLIC / job_id / str(ordinal)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Existing renderer is reliable and handles source media variations.
    render(source, clip["start"], clip["end"], segments, output_dir / "base.mp4", burn_subtitles=False)
    staged_broll = []
    staged_broll = []
    for i, piece in enumerate(timeline["layers"]["broll"]):
        asset = assets.get(piece["asset_id"])
        if not asset:
            log.warning("Skipping unregistered asset: %s", piece["asset_id"])
            continue
        # Normalize each licensed B-roll; preserve the creator's audio track.
        dest = output_dir / f"broll_{i}.mp4"
        try:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(piece["source_start"]),
                            "-i", str(asset["path"]), "-t", str(piece["duration"]),
                            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1",
                            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", str(dest)],
                           check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            log.warning("Skipping invalid B-roll %s: %s", piece["asset_id"], str(exc)[:200])
            dest.unlink(missing_ok=True)
            continue
        piece["path"] = dest.name
        staged_broll.append(piece)
    timeline["layers"]["broll"] = staged_broll
    write_timeline(target.with_suffix(".timeline.json"), timeline)
    # Manifest is also copied to Remotion's static directory so Chrome can load media.
    write_timeline(output_dir / "timeline.json", timeline)
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = os.getenv("RENDER_ENGINE", "remotion").lower()
    if engine == "ffmpeg":
        render(source, clip["start"], clip["end"], segments, target, burn_subtitles=True)
        return "ffmpeg_subtitled"
    props = {"jobId": job_id, "clipNo": str(ordinal), "timeline": timeline}
    props_path = output_dir / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    # The CLI uses absolute paths for props/output; only internally generated paths.
    try:
        subprocess.run(["./node_modules/.bin/remotion", "render", "src/index.tsx", "VerticalClip", str(target.resolve()),
                        "--props=" + str(props_path.resolve()), "--codec=h264", "--log=error"], cwd=RENDERER,
                       check=True, capture_output=True, text=True, timeout=int(os.getenv("RENDER_TIMEOUT", "900")))
        return "remotion"
    except (subprocess.SubprocessError, OSError) as exc:
        if os.getenv("RENDER_FALLBACK_FFMPEG", "true").lower() != "true":
            raise
        render(source, clip["start"], clip["end"], segments, target, burn_subtitles=True)
        return f"ffmpeg_subtitled_fallback: {str(exc)[:150]}"
