"""Conservative YouTube URL parsing and opt-in, permission-gated video acquisition."""
from __future__ import annotations
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_DURATION_SECONDS = int(os.getenv("YOUTUBE_MAX_DURATION", "7200"))
MAX_FILE_BYTES = int(os.getenv("YOUTUBE_MAX_BYTES", str(1_500_000_000)))


def normalize_youtube_url(url: str) -> str:
    """Produce one canonical HTTPS watch URL (no playlist, shortlinks or tracking)."""
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise ValueError("Use um link HTTPS do YouTube sem credenciais ou portas")
    host = (parts.hostname or "").lower().rstrip(".")
    if host not in YOUTUBE_HOSTS:
        raise ValueError("Somente URLs de vídeos do YouTube são aceitas")
    path = parts.path.rstrip("/")
    if host == "youtu.be":
        video_id = path.lstrip("/")
    elif path == "/watch":
        ids = parse_qs(parts.query).get("v", [])
        video_id = ids[0] if len(ids) == 1 else ""
    elif path.startswith(("/shorts/", "/live/", "/embed/")):
        video_id = path.split("/")[2] if len(path.split("/")) == 3 else ""
    else:
        video_id = ""
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError("URL inválida: informe o link de um único vídeo do YouTube")
    return f"https://www.youtube.com/watch?v={video_id}"


def download_youtube(url: str, destination: Path, *, source_snapshot: dict | None = None, settings: dict | None = None) -> tuple[Path, dict]:
    """Download only when platform authorization is expressly enabled.

    This function does not use cookies, private videos, login or anti-bot workarounds.
    Creator rights alone do not necessarily grant permission from YouTube.
    """
    if os.getenv("ENABLE_YOUTUBE_DOWNLOAD", "false").lower() != "true":
        raise PermissionError("Download por URL desabilitado; defina ENABLE_YOUTUBE_DOWNLOAD=true somente quando autorizado pelo YouTube e pelo titular")
    canonical = normalize_youtube_url(url)
    from yt_dlp import YoutubeDL
    destination.mkdir(parents=True, exist_ok=True)
    vid = canonical.split("v=")[-1]
    def verify_authorized_metadata(info):
        if source_snapshot is not None:
            from .source_ingestion import verify_source_metadata
            from .source_registry import get_source
            # Keep the original policy snapshot; revocation also stops future downloads.
            current = get_source(source_snapshot['channel_id'])
            verify_source_metadata(info, vid, current, settings or {})
            verify_source_metadata(info, vid, source_snapshot, settings or {})

    def media_filter(info, *, incomplete=False):
        if source_snapshot is not None and not incomplete:
            verify_authorized_metadata(info)
        return (
            "Vídeo maior que o limite permitido" if info.get("duration") and float(info["duration"]) > MAX_DURATION_SECONDS
            else "Live streams não são aceitos" if info.get("is_live") or info.get("live_status") == "is_live"
            else "Arquivo excede limite" if (info.get("filesize") or info.get("filesize_approx") or 0) > MAX_FILE_BYTES
            else None)
    template = str(destination / f"{vid}.%(ext)s")
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "js_runtimes": {"deno": {}},
        "extract_flat": False,
        "socket_timeout": 20,
        "retries": 2,
        "format": "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": template,
        "max_filesize": MAX_FILE_BYTES,
        "match_filter": media_filter,
    }
    with YoutubeDL(options) as ydl:
        metadata = ydl.extract_info(canonical, download=False)
        verify_authorized_metadata(metadata)
        if metadata.get("duration") and float(metadata["duration"]) > MAX_DURATION_SECONDS:
            raise ValueError("Vídeo excede o limite de duração")
        if metadata.get("is_live") or metadata.get("live_status") == "is_live":
            raise ValueError("Lives em andamento não são suportadas")
        ydl.params["skip_download"] = False
        data = ydl.extract_info(canonical, download=True)
        verify_authorized_metadata(data)
        actual = list(destination.glob(f"{vid}.*"))
        videos = [x for x in actual if x.is_file() and x.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
        if len(videos) != 1:
            raise RuntimeError("Não foi possível identificar exatamente um arquivo de vídeo")
        filepath = videos[0]
        if filepath.stat().st_size > MAX_FILE_BYTES:
            filepath.unlink(missing_ok=True)
            raise ValueError("Arquivo excedeu limite de tamanho")
        result = {"title": data.get("title") or vid, "video_id": vid, "channel": data.get("channel") or data.get("uploader") or "", "source_url": canonical, "duration": data.get("duration"), "channel_id":data.get('channel_id'), 'language':data.get('language')}
        if source_snapshot is not None:
            from .source_ingestion import verify_source_metadata
            result.update(verify_source_metadata(data,vid,source_snapshot,settings or {}))
        return filepath, result
