"""Dedicated scheduler configuration and Meta credential loading."""
from __future__ import annotations

import os
import json
import subprocess
import logging
import math
import time
import threading
from fractions import Fraction
from pathlib import Path

from . import meta_http, meta_transport, publication_schedule, store


class ConfigurationError(RuntimeError):
    pass


def settings() -> dict:
    return {'credential_file': os.getenv('META_CREDENTIAL_FILE', '/run/secrets/meta.env'),
            'graph_version': os.getenv('META_GRAPH_VERSION', 'v27.0')}


def read_user_token() -> str:
    try:
        lines = Path(settings()['credential_file']).read_text(encoding='utf-8-sig').splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError('Não foi possível ler as credenciais Meta') from exc
    tokens = []
    for line in lines:
        if not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            if key.strip() == 'USER_ACCESS_TOKEN':
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                tokens.append(value)
    if len(tokens) != 1 or not tokens[0] or any(c in tokens[0] for c in '\r\n'):
        raise ConfigurationError('Token Meta ausente ou duplicado')
    return tokens[0]


def check_video(path: Path, provider: str) -> None:
    """Reject incompatible files before creating a remote upload session."""
    try:
        if not path.is_file() or path.stat().st_size <= 0 or (provider == 'instagram' and path.stat().st_size > 300_000_000):
            raise ValueError('invalid file size')
        raw = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                                      'format=format_name,duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,bit_rate,pix_fmt,field_order',
                                      '-of', 'json', str(path)], timeout=30)
        result = json.loads(raw)
        video = next(s for s in result['streams'] if s['codec_type'] == 'video')
        duration = float(result['format']['duration'])
        fps = float(Fraction(video['r_frame_rate']))
        width, height = int(video['width']), int(video['height'])
        if not math.isfinite(duration) or not math.isfinite(fps) or duration < 3 or fps < 23 or fps > 60 or width <= 0 or height <= 0 or width > 1920:
            raise ValueError('unsupported duration, frame rate or resolution')
        if provider == 'instagram':
            if duration > 900 or video['codec_name'] not in ('h264', 'hevc') or 'mp4' not in result['format']['format_name']:
                raise ValueError('unsupported Instagram format')
            if video.get('pix_fmt') != 'yuv420p' or video.get('field_order') not in ('progressive', 'unknown', None):
                raise ValueError('unsupported Instagram pixel format or scan')
            if int(video.get('bit_rate', 0)) > 25_000_000:
                raise ValueError('unsupported Instagram video bitrate')
            audio = [s for s in result['streams'] if s['codec_type'] == 'audio']
            if any(s['codec_name'] != 'aac' or int(s['sample_rate']) > 48000 or int(s.get('channels', 0)) not in (1, 2) for s in audio):
                raise ValueError('unsupported Instagram audio')
        elif provider == 'facebook':
            if duration < 4 or duration > 60 or width < 540 or height < 960 or width * 16 != height * 9:
                raise ValueError('unsupported Facebook Reel')
        else:
            raise ValueError('unsupported provider')
    except (OSError, subprocess.SubprocessError, KeyError, StopIteration, TypeError, ZeroDivisionError, ValueError) as exc:
        raise ConfigurationError('Vídeo incompatível com o destino ou inspeção indisponível') from exc


def transport(draft: dict, job: dict, destination: dict, progress=lambda *_: None) -> dict:
    try:
        matches = [c for c in job['candidates'] if c.get('candidate_id') == draft['candidate_id']]
        if len(matches) != 1:
            raise ConfigurationError('Candidato não encontrado')
        path = Path(matches[0]['file'])
        provider = draft['provider']
        check_video(path, provider)
        api = meta_http.MetaHTTP(settings()['graph_version'])
        page_token = meta_http.resolve_page(api, destination['page_id'], destination['instagram_id'], read_user_token())
    except ConfigurationError as exc:
        raise publication_schedule.PreflightError(str(exc)) from exc
    except meta_http.MetaHTTPError as exc:
        raise publication_schedule.PreflightError(f'Falha ao validar acesso Meta: {exc}') from exc
    except (ValueError, KeyError) as exc:
        raise publication_schedule.PreflightError('A conta de destino não pôde ser validada') from exc
    except Exception as exc:
        raise publication_schedule.PreflightError('Falha de conexão ao validar a conta Meta') from exc
    if provider == 'instagram':
        return meta_transport.instagram(api, destination['instagram_id'], page_token, path, draft['description'], progress=progress)
    return meta_transport.facebook(api, page_token, path, draft['description'], title=draft['title'], progress=progress)


def run_once() -> None:
    for item in publication_schedule.due_items():
        try:
            publication_schedule.execute(item['id'], transport)
        except ValueError:
            # Another operation may have cancelled the item between list and claim.
            continue


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    publication_schedule.ROOT.mkdir(parents=True, exist_ok=True)
    # One process owns the dispatcher for its entire lifetime.
    with store.file_lock(publication_schedule.ROOT / 'worker.lock'):
        publication_schedule.recover_interrupted()
        def heartbeat():
            while True:
                try:
                    publication_schedule.write_heartbeat()
                except OSError:
                    logging.error('Não foi possível atualizar o estado da agenda')
                time.sleep(10)
        threading.Thread(target=heartbeat, daemon=True).start()
        while True:
            try:
                run_once()
            except Exception:
                logging.error('Falha no ciclo da agenda; verifique os registros locais')
            time.sleep(5)


if __name__ == '__main__':
    main()
