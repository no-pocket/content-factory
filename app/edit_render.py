"""FFmpeg stages media, Remotion composes animated layers. No model-supplied paths.

The exact timeline is stored next to each candidate for reproducibility.
"""
from __future__ import annotations
import json
import os
import subprocess
import logging
import uuid
from pathlib import Path

from .core import render, get_duration
from .timeline import ASSET_ID, validate_timeline, write_timeline

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


def browser_preview(source: Path) -> tuple[Path, str]:
    """Prefer the browser-native preview, retaining MP4 as the download master."""
    preview = source.with_suffix('.preview.webm')
    return (preview, 'video/webm') if preview.is_file() else (source, 'video/mp4')


def make_web_preview(source: Path, *, quality: str = 'standard') -> Path:
    """Write a VP8/Opus preview only after the complete file decodes successfully."""
    preview = source.with_suffix('.preview.webm')
    pending = source.with_name(f'{source.stem}.preview.{uuid.uuid4().hex}.webm')
    try:
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
            '-map', '0:v:0', '-map', '0:a:0?', '-vf', 'scale=720:-2' if quality == 'high' else 'scale=540:-2',
            '-c:v', 'libvpx', '-deadline', 'realtime', '-cpu-used', '8',
            '-b:v', '4000k' if quality == 'high' else '1500k', '-crf', '10' if quality == 'high' else '24', '-threads', '4', '-pix_fmt', 'yuv420p',
            '-c:a', 'libopus', '-b:a', '96k', str(pending),
        ], check=True, capture_output=True, text=True)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror',
                        '-i', str(pending), '-f', 'null', '-'],
                       check=True, capture_output=True, text=True)
        os.replace(pending, preview)
        return preview
    finally:
        pending.unlink(missing_ok=True)


def apply_finishing(target: Path, timeline: dict, *, quality: str = 'standard') -> None:
    """Add an outro after all speech; legacy timelines keep their original bytes."""
    ending = timeline.get('finishing')
    if not ending:
        return
    # Called after timeline validation; times are bounded numeric values, not expressions.
    tail, fade = ending['tail_seconds'], ending['fade_seconds']
    duration = get_duration(target)
    pending = target.with_name(f'{target.stem}.ending.{uuid.uuid4().hex}.mp4')
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(target),
                        '-map', '0:v:0', '-map', '0:a:0?',
                        '-vf', f'tpad=stop_mode=clone:stop_duration={tail},fade=t=out:st={duration+tail-fade}:d={fade}',
                        '-af', f'apad=pad_dur={tail}', '-t', str(duration+tail),
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18' if quality == 'high' else '24',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(pending)],
                       check=True, capture_output=True, text=True)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def render_edited(source: Path, job_id: str, ordinal: int, clip: dict, segments: list[dict], timeline: dict, assets: dict, target: Path, *, engine: str | None = None, quality: str = 'standard', metrics: list | None = None, metric_context: dict | None = None, finishing_mode: str = 'post_encode', outro_asset_id: str | None = None, outro_snapshot: dict | None = None) -> str:
    """Use FFmpeg for normalization and Remotion for visual edits, fallback if configured."""
    validate_timeline(timeline)
    if finishing_mode not in ('post_encode','remotion'):
        raise ValueError('Invalid finishing mode')
    from .telemetry import measure_stage
    metrics = metrics if metrics is not None else []
    metric_context = metric_context or {'job_id':job_id,'render_revision':clip.get('render_revision','UNKNOWN'),
                                       'configuration_sha256':'UNKNOWN','component_snapshot_id':'UNKNOWN'}
    framing_options = {}
    if timeline.get('framing') or timeline.get('framing_schedule'):
        from .framing import validate_framing, validate_framing_schedule
        size = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                         '-show_entries', 'stream=width,height', '-of', 'json', str(source)]))['streams'][0]
        if timeline.get('framing'):
            timeline['framing_resolved'] = validate_framing(timeline['framing'], (size['width'],size['height']), (720,1280))
            framing_options['framing'] = timeline['framing_resolved']
        if timeline.get('framing_schedule'):
            timeline['framing_schedule'] = validate_framing_schedule(timeline['framing_schedule'], timeline['duration'], (size['width'],size['height']))
            framing_options['framing_schedule'] = timeline['framing_schedule']
    output_dir = PUBLIC / job_id / str(ordinal)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Existing renderer is reliable and handles source media variations.
    multisegment = timeline['schema_version'] == '3.0'
    with measure_stage(metrics,'BASE',metric_context,requested='ffmpeg',resolved='ffmpeg'):
        if multisegment:
            from .assembly import render_assembly
            fields = ('schema_version','fps','duration','source_duration','segments','reorder_approval')
            plan = render_assembly(source, {key: timeline[key] for key in fields if key in timeline},
                                   output_dir / 'base.mp4', quality=quality, **framing_options)
            timeline['segments'] = plan['segments']
        else:
            render(source, clip["start"], clip["end"], segments, output_dir / "base.mp4", burn_subtitles=False, crf=16 if quality == 'high' else 24, **framing_options)
    staged_broll = []
    for i, piece in enumerate(timeline["layers"]["broll"]):
        if multisegment and any(s.get('framing', {}).get('preset') in {'web','tweet','document'} and
                               max(piece['at'],s['output_start']) < min(piece['at']+piece['duration'],s['output_start']+s['duration'])
                               for s in timeline['segments']):
            log.warning('Skipping B-roll over protected source evidence')
            continue
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
    engine = (engine if engine is not None else os.getenv("RENDER_ENGINE", "remotion")).lower()
    compose_finishing = finishing_mode=='remotion' and engine=='remotion' and bool(timeline.get('finishing'))
    def subtitled_output():
        if multisegment:
            from .core import write_srt
            subtitle = target.with_suffix('.srt')
            write_srt([{'start':0,'end':timeline['duration'],'words':timeline['layers']['captions']}],0,timeline['duration'],subtitle)
            args = ['ffmpeg','-nostdin','-v','error','-y','-i',str((output_dir/'base.mp4').resolve()),'-map','0:v:0','-map','0:a?']
            if subtitle.stat().st_size:
                args += ['-vf',"subtitles="+subtitle.name+":force_style='FontName=DejaVu Sans,FontSize=15,Outline=2,Shadow=1,Alignment=2,MarginV=55'"]
            args += ['-c:v','libx264','-preset','veryfast','-crf','18' if quality=='high' else '24',
                     '-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(target.resolve())]
            subprocess.run(args,check=True,capture_output=True,text=True,cwd=target.parent)
        else:
            render(source, clip["start"], clip["end"], segments, target, burn_subtitles=True, crf=18 if quality == 'high' else 24, **framing_options)
    def finish_outro():
        if outro_asset_id is not None:
            from .outro import append_outro, validate_job_outro
            validate_job_outro({'settings':{'outro_asset_id':outro_asset_id},
                                'outro_snapshot':outro_snapshot}, assets)
            clip['outro'] = append_outro(target, outro_asset_id, assets, quality=quality,
                expected_sha256=outro_snapshot['sha256'])
            timeline['outro'] = clip['outro']
            write_timeline(target.with_suffix('.timeline.json'), timeline)
    if engine == "ffmpeg":
        with measure_stage(metrics,'REMOTION',metric_context,requested='ffmpeg',resolved='ffmpeg_subtitled') as metric:
            metric['state']='SKIPPED'
        with measure_stage(metrics,'SUBTITLES',metric_context,requested='ffmpeg',resolved='ffmpeg_subtitled'):
            subtitled_output()
        with measure_stage(metrics,'FINISHING',metric_context,requested='post_encode',resolved='post_encode'):
            apply_finishing(target, timeline, quality=quality)
        finish_outro()
        with measure_stage(metrics,'PREVIEW',metric_context,requested='webm',resolved='vp8_opus'):
            make_web_preview(target, quality=quality)
        return "ffmpeg_subtitled"
    props = {"jobId": job_id, "clipNo": str(ordinal), "timeline": timeline, 'composeFinishing':compose_finishing}
    props_path = output_dir / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    # The CLI uses absolute paths for props/output; only internally generated paths.
    try:
        with measure_stage(metrics,'REMOTION',metric_context,requested='remotion',resolved='remotion') as render_metric:
            subprocess.run(["./node_modules/.bin/remotion", "render", "src/index.tsx", "VerticalClip", str(target.resolve()),
                            "--props=" + str(props_path.resolve()), "--codec=h264", "--log=error", *(["--crf=18"] if quality == "high" else [])], cwd=RENDERER,
                           check=True, capture_output=True, text=True, timeout=int(os.getenv("RENDER_TIMEOUT", "900")))
        renderer_used = "remotion"
    except (subprocess.SubprocessError, OSError) as exc:
        if quality == "high" or os.getenv("RENDER_FALLBACK_FFMPEG", "true").lower() != "true":
            render_metric.update(resolved='NONE',fallback_reason='disabled_for_high_fidelity' if quality=='high' else 'fallback_disabled')
            raise
        compose_finishing=False
        render_metric.update(resolved='ffmpeg_subtitled',fallback_reason=type(exc).__name__)
        with measure_stage(metrics,'SUBTITLES',metric_context,requested='remotion',resolved='ffmpeg_subtitled',fallback_reason=type(exc).__name__):
            subtitled_output()
        renderer_used = f"ffmpeg_subtitled_fallback: {str(exc)[:150]}"
    with measure_stage(metrics,'FINISHING',metric_context,requested=finishing_mode,
                       resolved='remotion_composition' if compose_finishing else 'post_encode') as metric:
        if compose_finishing:
            metric.update(state='INTEGRATED',included_in_stage='REMOTION')
        else:
            apply_finishing(target, timeline, quality=quality)
    finish_outro()
    with measure_stage(metrics,'PREVIEW',metric_context,requested='webm',resolved='vp8_opus'):
        make_web_preview(target, quality=quality)
    return renderer_used
