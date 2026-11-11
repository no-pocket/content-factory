"""Backend-owned render identities and immutable version paths."""
from __future__ import annotations

import copy
import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path

from . import store
from .editorial_contracts import candidate_key


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def render_target(job: dict, index: int, revision: int | None = None) -> Path:
    # Validate IDs before using them in a path; no paths from model/client input.
    cid = candidate_key(job['id'], index)
    clip = job['candidates'][index]
    if job.get('editorial_protocol', 1) != 2:
        return store.OUTPUT / job['id'] / f'candidate_{index+1}.mp4'
    rev = revision if revision is not None else clip.get('render_revision', 0) + 1
    if type(rev) is not int or rev < 1:
        raise ValueError('Invalid render revision')
    return store.OUTPUT / job['id'] / cid / f'render_{rev}' / 'master.mp4'


@lru_cache(maxsize=2048)
def _presentation_file_hash(path: str, fingerprint: tuple) -> str:
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def artifact_manifest(job: dict, index: int, *, presentation_cache: bool = False) -> dict:
    clip = job['candidates'][index]
    cid = candidate_key(job['id'], index)
    root = (store.OUTPUT / job['id']).resolve()
    manifest = {'candidate_id': clip.get('candidate_id', cid), 'candidate_version': clip.get('candidate_version', 1),
                'render_revision': clip.get('render_revision', 1), 'plan_sha256': _plan_hash(clip), 'files': {}}
    master = Path(clip['file']) if clip.get('file') else None
    paths = {'mp4': master, 'webm': master.with_suffix('.preview.webm') if master else None,
             'timeline': Path(clip['timeline_file']) if clip.get('timeline_file') else
                         master.with_suffix('.timeline.json') if master else None}
    for kind, path in paths.items():
        if path is None:
            manifest['files'][kind] = None
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError('Artifact outside job output directory')
        if not resolved.is_file():
            manifest['files'][kind] = None
            continue
        if presentation_cache:
            stat=resolved.stat()
            checksum=_presentation_file_hash(str(resolved),(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,int(time.monotonic()//2)))
        else:
            with resolved.open('rb') as handle:
                checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
        manifest['files'][kind] = {'path': resolved.relative_to(root).as_posix(), 'sha256': checksum}
    return manifest


def _plan_hash(clip: dict) -> str:
    return digest({key: clip.get(key) for key in ('start', 'end', 'timeline')})


def register_render(job: dict, index: int, *, revision: int | None = None) -> None:
    """Register a completed attempt; retain prior manifests/events, even after failure."""
    clip = job['candidates'][index]
    if clip.get('artifact_manifest'):
        clip.setdefault('render_history', []).append(copy.deepcopy({
            k: clip[k] for k in ('artifact_manifest', 'artifact_id', 'render_revision', 'candidate_version')}))
        if 'social_captions' in clip:
            clip.setdefault('social_caption_history', []).append({
                'artifact_id': clip.get('artifact_id'), 'suggestions': copy.deepcopy(clip['social_captions'])})
            del clip['social_captions']
    clip.setdefault('candidate_id', candidate_key(job['id'], index))
    clip.setdefault('candidate_version', 1)
    previous_plan = clip.get('artifact_manifest', {}).get('plan_sha256')
    if previous_plan is not None and previous_plan != _plan_hash(clip):
        clip['parent_candidate_version'] = clip['candidate_version']
        clip['candidate_version'] += 1
    next_revision = clip.get('render_revision', 0) + 1
    if revision is not None and (type(revision) is not int or revision < next_revision):
        raise ValueError('Render revisions must increase')
    clip['render_revision'] = revision if revision is not None else next_revision
    manifest = artifact_manifest(job, index)
    clip.update(artifact_manifest=manifest, artifact_id='sha256:' + digest(manifest))
    # A revision invalidates current approval without modifying its historical event.
    job['approved'] = [i for i in job.get('approved', []) if i != index]
