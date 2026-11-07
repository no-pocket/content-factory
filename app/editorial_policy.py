"""Versioned local briefs: drafts never become active without explicit approval."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid

from . import store
from .artifacts import digest

ROOT = store.ROOT / 'editorial'


class PolicyConflict(ValueError):
    pass


def initial_brief() -> dict:
    return {'schema_version': '1.0', 'id': 'editorial-brief-v1', 'parent_id': None,
            'status': 'DRAFT', 'scope': 'GTA_VI',
            'priorities': ['Novidades, análises, descobertas e demonstrações com evidência',
                           'Cumprir a promessa e concluir a ideia; duração subordinada à história'],
            'penalties': ['Autopromoção dominante', 'Promessa sem demonstração ou conclusão'],
            'visual_rules': ['Preservar informação visual e legendas sincronizadas'],
            'title_rules': ['Título distinto da fala, apoiado na evidência'],
            'feedback_references': [], 'author': 'content-factory-plan', 'approval': None}


def _path(ident: str) -> Path:
    if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', ident):
        raise ValueError('Invalid brief ID')
    root = (ROOT / 'briefs').resolve()
    path = (root / (ident+'.json')).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Invalid brief path')
    return path


def _atomic(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        pending.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def _validate(brief):
    template = initial_brief()
    if not isinstance(brief, dict) or set(brief) != set(template) or brief['schema_version'] != '1.0':
        raise ValueError('Invalid brief fields')
    _path(brief['id'])
    if brief['parent_id'] is not None:
        _path(brief['parent_id'])
    if brief['status'] not in ('DRAFT', 'APPROVED', 'RETIRED') or brief['scope'] != 'GTA_VI':
        raise ValueError('Invalid brief status/scope')
    for key in ('priorities', 'penalties', 'visual_rules', 'title_rules', 'feedback_references'):
        if not isinstance(brief[key], list) or len(brief[key]) > 50 or any(not isinstance(v, str) or not 0 < len(v) <= 1000 for v in brief[key]):
            raise ValueError('Invalid brief rule/reference')
    if not isinstance(brief['author'], str) or not 0 < len(brief['author']) <= 200:
        raise ValueError('Invalid brief author')


def save_policy_draft(brief: dict) -> dict:
    _validate(brief)
    if brief['status'] != 'DRAFT' or brief['approval'] is not None:
        raise ValueError('Only an unapproved draft may be proposed')
    ROOT.mkdir(parents=True, exist_ok=True)
    with store.file_lock(ROOT / 'policy.lock'):
        path = _path(brief['id'])
        if path.exists():
            raise FileExistsError('Brief IDs are immutable; propose a new ID with parent_id')
        _atomic(path, brief)
    return copy.deepcopy(brief)


def resolve_policy(policy_id: str | None) -> dict:
    pointer = ROOT / 'active_policy.json'
    active = json.loads(pointer.read_text(encoding='utf-8')) if pointer.is_file() else {'revision': 0, 'brief_id': None}
    ident = policy_id if policy_id is not None else active['brief_id']
    if ident is None:
        return {'status': 'NONE', 'revision': active['revision'], 'brief': None, 'brief_id': 'UNKNOWN', 'brief_sha256': 'UNKNOWN'}
    brief = json.loads(_path(ident).read_text(encoding='utf-8'))
    _validate(brief)
    if brief['status'] != 'APPROVED' or not brief['approval']:
        raise ValueError('Brief is not explicitly approved')
    checksum = digest(brief)
    if ident == active['brief_id'] and active.get('brief_sha256') != checksum:
        raise PolicyConflict('Active brief bytes changed')
    return {'status': 'APPROVED', 'revision': active['revision'], 'brief_id': ident,
            'brief_sha256': checksum, 'brief': copy.deepcopy(brief)}


def approve_policy(policy_candidate_id: str, expected_revision: int, actor: str) -> dict:
    """Explicit human operation, also used to roll back to a previously approved ID."""
    if type(expected_revision) is not int or expected_revision < 0 or not isinstance(actor, str) or not 0 < len(actor.strip()) <= 200:
        raise ValueError('Expected revision and human actor required')
    ROOT.mkdir(parents=True, exist_ok=True)
    with store.file_lock(ROOT / 'policy.lock'):
        pointer = ROOT / 'active_policy.json'
        previous = json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else {'revision': 0}
        if previous['revision'] != expected_revision:
            raise PolicyConflict('Stale policy revision')
        path = _path(policy_candidate_id)
        brief = json.loads(path.read_text(encoding='utf-8'))
        _validate(brief)
        if brief['status'] == 'RETIRED':
            raise ValueError('Retired brief cannot be activated')
        if brief['status'] == 'DRAFT':
            brief.update(status='APPROVED', approval={'actor': actor, 'at': datetime.now(timezone.utc).isoformat()})
            _atomic(path, brief)
        active = {'revision': expected_revision+1, 'brief_id': brief['id'], 'brief_sha256': digest(brief),
                  'actor': actor, 'parent_revision': previous['revision']}
        _atomic(pointer, active)
        return active
