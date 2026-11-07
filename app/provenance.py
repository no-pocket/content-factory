"""Small immutable creation-time component snapshot; unavailable facts stay UNKNOWN."""
from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def component_snapshot(settings: dict) -> dict:
    from .artifacts import digest
    def git(*args):
        try:
            return subprocess.check_output(['git', '--no-optional-locks', '-c', 'safe.directory='+str(ROOT), *args], cwd=ROOT, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
    head = git('rev-parse', 'HEAD')
    patch = git('diff', 'HEAD', '--binary', '--', 'app', 'renderer', 'contracts', 'requirements.txt', 'Dockerfile')
    untracked = git('ls-files', '--others', '--exclude-standard', '--', 'app', 'renderer/src', 'contracts')
    if patch is not None and untracked is not None:
        dirty = hashlib.sha256(patch)
        for name in sorted(untracked.decode().splitlines()):
            path = ROOT / name
            if path.is_file():
                dirty.update(name.encode())
                dirty.update(path.read_bytes())
        patch_hash = dirty.hexdigest()
    else:
        patch_hash = 'UNKNOWN'
    prompts = {}
    for name in ('ranker', 'director'):
        path = ROOT / 'app' / (name+'.py')
        prompts[name] = {'id': 'director-source-table-v2' if name == 'director' else name+'-full-context-v1', 'module_sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'UNKNOWN'}
    packages = {}
    for name in ('streamlit', 'faster-whisper', 'redis'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = 'UNKNOWN'
    import os
    file_hashes={}
    for name in ('app/core.py','app/edit_render.py','app/candidates.py','app/worker.py','app/telemetry.py',
                 'app/job_settings.py','app/provenance.py','app/timeline.py','app/assembly.py','app/framing.py','renderer/src/vertical-clip.tsx',
                 'renderer/src/index.tsx','requirements.lock','renderer/package-lock.json'):
        path=ROOT/name
        file_hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'UNKNOWN'
    snapshot = {'schema_version': '1.0', 'git_head': head.decode().strip() if head else os.getenv('CONTENT_FACTORY_GIT_HEAD','UNKNOWN'),
                'dirty_patch_sha256': patch_hash, 'prompts': prompts, 'dependencies': packages,
                'component_file_hashes':file_hashes,'build_source_sha256':os.getenv('CONTENT_FACTORY_SOURCE_SHA256','UNKNOWN'),
                'model_requested': settings['llm_model'], 'model_resolved': 'UNKNOWN',
                'backend_requested': settings['llm_backend'], 'context_window': None if settings['llm_backend'] == 'external' else 4096 if settings['llm_backend'] == 'kepler_gpu' else 8192,
                'renderer_requested': settings['render_engine'], 'timeline_schema': '3.0' if settings.get('timeline_v3') else '2.0',
                'ranker_rules': 'full-context-v1', 'retrieval': None, 'dataset': None}
    return {**snapshot, 'snapshot_id': digest(snapshot)}
