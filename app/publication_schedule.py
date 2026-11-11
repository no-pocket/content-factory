"""Persistent local publication intentions; this module does not transmit media."""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path

from . import publishing, service, store

ROOT = store.ROOT / 'publication_schedule'


class PreflightError(RuntimeError):
    """A local or read-only prerequisite failed before any remote mutation."""


def _path(identifier: str) -> Path:
    parsed = uuid.UUID(identifier)
    if str(parsed) != identifier:
        raise ValueError('invalid schedule id')
    return ROOT / (identifier + '.json')


def _save(item: dict) -> None:
    target = _path(item['id'])
    temporary = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(item, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def schedule(jid: str, candidate_id: str, provider: str, *, title: str, caption: str, scheduled_at: float, page_id: str, instagram_id: str | None = None, timezone_name: str = 'America/Sao_Paulo') -> dict:
    if provider not in ('instagram', 'facebook'):
        raise ValueError('unsupported platform')
    if not isinstance(page_id, str) or not page_id.isdecimal() or (provider == 'instagram' and (not isinstance(instagram_id, str) or not instagram_id.isdecimal())):
        raise ValueError('invalid destination')
    if provider == 'facebook':
        instagram_id = None
    from zoneinfo import ZoneInfo
    ZoneInfo(timezone_name)
    if isinstance(scheduled_at, bool) or not isinstance(scheduled_at, (int, float)) or not math.isfinite(scheduled_at) or scheduled_at <= 0:
        raise ValueError('invalid schedule time')
    ROOT.mkdir(parents=True, exist_ok=True)
    with store.job_lock(jid):
        draft = publishing.build_draft(store.load(jid), candidate_id, provider, title=title, description=caption)
        item = {'id': str(uuid.uuid4()), 'state': 'SCHEDULED', 'scheduled_at': scheduled_at,
                'created_at': time.time(), 'draft': draft, 'remote_id': None, 'timezone': timezone_name,
                'destination': {'page_id': page_id, 'instagram_id': instagram_id}}
        with store.file_lock(ROOT / 'schedule.lock'):
            for existing in list_items():
                if (existing['state'] != 'CANCELLED' and existing['scheduled_at'] == scheduled_at
                        and existing['draft'] == draft and existing.get('destination') == item['destination']):
                    return existing
            _save(item)
    return item


def list_items() -> list[dict]:
    if not ROOT.exists():
        return []
    return sorted((json.loads(p.read_text(encoding='utf-8')) for p in ROOT.glob('*.json')),
                  key=lambda row: row['scheduled_at'])


def due_items(*, now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    return [item for item in list_items() if item['state'] == 'SCHEDULED' and item['scheduled_at'] <= now]


def write_heartbeat(*, now: float | None = None) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / 'worker.heartbeat'
    temporary = ROOT / ('heartbeat.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(str(time.time() if now is None else now), encoding='utf-8')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def worker_online(*, now: float | None = None) -> bool:
    try:
        elapsed = (time.time() if now is None else now) - float((ROOT / 'worker.heartbeat').read_text(encoding='utf-8'))
        return 0 <= elapsed <= 40
    except (OSError, ValueError):
        return False


def recover_interrupted() -> None:
    """Called by the sole worker after restart, never repeat unknown remote effects."""
    with store.file_lock(ROOT / 'schedule.lock'):
        for path in ROOT.glob('*.json'):
            item = json.loads(path.read_text(encoding='utf-8'))
            if item['state'] in ('SENDING', 'PROCESSING', 'PUBLISHING'):
                item.update(state='UNCERTAIN', error='Serviço interrompido; reconciliação remota necessária')
                _save(item)


def cancel(identifier: str) -> dict:
    path = _path(identifier)
    with store.file_lock(ROOT / 'schedule.lock'):
        item = json.loads(path.read_text(encoding='utf-8'))
        if item['state'] != 'SCHEDULED':
            raise ValueError('only pending schedules can be cancelled')
        item['state'] = 'CANCELLED'
        _save(item)
        return item


def reschedule(identifier: str, scheduled_at: float, timezone_name: str) -> dict:
    from zoneinfo import ZoneInfo
    ZoneInfo(timezone_name)
    if isinstance(scheduled_at, bool) or not isinstance(scheduled_at, (int, float)) or not math.isfinite(scheduled_at) or scheduled_at <= 0:
        raise ValueError('invalid schedule time')
    path = _path(identifier)
    with store.file_lock(ROOT / 'schedule.lock'):
        item = json.loads(path.read_text(encoding='utf-8'))
        if item['state'] != 'SCHEDULED':
            raise ValueError('only pending schedules can be changed')
        item.update(scheduled_at=scheduled_at, timezone=timezone_name)
        _save(item)
        return item


def execute(identifier: str, transport, *, now: float | None = None) -> dict:
    """Claim a due item once. An interrupted claim requires manual reconciliation."""
    path = _path(identifier)
    with store.file_lock(ROOT / 'schedule.lock'):
        item = json.loads(path.read_text(encoding='utf-8'))
        if item['state'] != 'SCHEDULED' or item['scheduled_at'] > (time.time() if now is None else now):
            raise ValueError('schedule is not due')
        item['state'] = 'SENDING'
        _save(item)
    draft = item['draft']
    def progress(state: str, remote_id: str) -> None:
        if state not in ('SENDING', 'PROCESSING', 'PUBLISHING') or not str(remote_id).isdecimal():
            raise ValueError('invalid remote progress')
        with store.file_lock(ROOT / 'schedule.lock'):
            item['state'] = state
            item['remote_container_id'] = str(remote_id)
            _save(item)
    try:
        with store.job_lock(draft['job_id']):
            job = store.load(draft['job_id'])
            current = publishing.build_draft(job, draft['candidate_id'], draft['provider'],
                                             title=draft['title'], description=draft['description'])
            if any(current[key] != draft[key] for key in ('artifact_id', 'review_event_id', 'candidate_version', 'render_revision')):
                raise service.Conflict('Aprovação ou artefato alterado')
            try:
                result = transport(current, job, item['destination'], progress)
            except PreflightError:
                raise
            except Exception as exc:
                raise RuntimeError('Falha de transporte; resultado incerto') from exc
            if not isinstance(result, dict) or not result.get('remote_id') or not result.get('confirmed'):
                raise RuntimeError('Resultado remoto não confirmado')
        item.update(state='PUBLISHED', remote_id=str(result['remote_id']), permalink=result.get('permalink'), published_at=time.time())
    except PreflightError as exc:
        item.update(state='BLOCKED', error=str(exc))
    except (service.Conflict, ValueError, FileNotFoundError):
        item.update(state='BLOCKED', error='Aprovação, QC ou arquivo não estão válidos')
    except Exception:
        item.update(state='UNCERTAIN', error='Resultado não confirmado; reconciliação necessária')
    with store.file_lock(ROOT / 'schedule.lock'):
        _save(item)
    return item
