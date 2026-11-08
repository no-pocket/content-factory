"""Local publication draft outbox, bound to a currently approved render.

This foundation deliberately has no OAuth or external publication action.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid

from . import service, store
from .artifacts import artifact_manifest, digest
from .publishing_adapters import PROVIDERS, request_plan

ROOT = store.ROOT / 'publishing'


def connection_status(provider: str) -> dict:
    if provider not in PROVIDERS:
        raise ValueError('Unknown publishing provider')
    spec = PROVIDERS[provider]
    missing = [key for key in spec['env'] if not os.getenv(key, '').strip()]
    return {'provider': provider, 'label': spec['label'],
            'state': 'NOT_CONFIGURED' if missing else 'CONFIGURED_UNVERIFIED',
            'missing': missing, 'requirements': spec['requirements'], 'mode': 'dry-run'}


def build_draft(job: dict, candidate_id: str, provider: str, *, title: str, description: str = '') -> dict:
    if provider not in PROVIDERS:
        raise ValueError('Unknown publishing provider')
    title_limit = 100 if provider == 'youtube' else 255
    if not isinstance(title, str) or not title.strip() or len(title) > title_limit or any(c in title for c in '<>'):
        raise ValueError(f'Título obrigatório, até {title_limit} caracteres, sem < ou >')
    if not isinstance(description, str) or len(description) > (5000 if provider == 'youtube' else 2200):
        raise ValueError('Descrição excede limite do conector')
    if provider == 'tiktok' and len((description or title).encode('utf-16-le')) // 2 > 2200:
        raise ValueError('Legenda TikTok excede 2200 unidades UTF-16')
    if job.get('editorial_protocol') != 2:
        raise service.Conflict('Publicação requer revisão humana v2 vinculada ao artefato atual')
    row = next((r for r in service.get_editorial_view(job)['candidates'] if r['candidate_id'] == candidate_id), None)
    if row is None:
        raise ValueError('Unknown candidate')
    event = row.get('current_event')
    if not row['artifact_intact'] or row['normalized_decision'] != 'APPROVED' or not event or event.get('actor', {}).get('kind') != 'human':
        raise service.Conflict('Candidato precisa de aprovação humana integral do render atual')
    if any(e.get('status') == 'OPEN' and e.get('severity') in ('MAJOR', 'CRITICAL') for e in event.get('edit_requests', [])):
        raise service.Conflict('Ajustes importantes ainda pendentes')
    index = row['original_index']
    if not service.verify_reviewable(job, index):
        raise service.Conflict('QC atual não permite preparar publicação')
    manifest = artifact_manifest(job, index)
    if 'sha256:' + digest(manifest) != row['artifact_id']:
        raise service.Conflict('Artefato mudou durante o preflight')
    master = Path(job['candidates'][index]['file'])
    size = master.stat().st_size
    if not size:
        raise service.Conflict('MP4 vazio')
    return {'schema_version': '1.0', 'job_id': job['id'], 'candidate_id': candidate_id,
            'candidate_version': row['candidate_version'], 'render_revision': row['render_revision'],
            'artifact_id': row['artifact_id'], 'artifact_manifest': manifest,
            'review_event_id': event['event_id'], 'editorial_revision': job.get('editorial_revision', 0),
            'provider': provider, 'title': title.strip(), 'description': description, 'mp4_bytes': size,
            'plan': request_plan(provider, title=title.strip(), description=description, size=size)}


def queue_dry_run(jid: str, candidate_id: str, provider: str, *, title: str, description: str = '') -> dict:
    with store.job_lock(jid):
        draft = build_draft(store.load(jid), candidate_id, provider, title=title, description=description)
        key = digest(draft)
        ROOT.mkdir(parents=True, exist_ok=True)
        path = ROOT / (key + '.json')
        with store.file_lock(ROOT / 'outbox.lock'):
            if path.exists():
                return json.loads(path.read_text(encoding='utf-8'))
            item = {'draft_id': key, 'state': 'DRY_RUN', 'created_at': time.time(), 'remote_id': None, 'draft': draft}
            pending = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            try:
                pending.write_text(json.dumps(item, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                os.replace(pending, path)
            finally:
                pending.unlink(missing_ok=True)
            return item


def render_publishing_panel(st, jobs: list[dict]) -> None:
    with st.expander('Publicação — Instagram, Facebook, YouTube e TikTok'):
        st.caption('Rascunhos locais: nenhum upload, login ou publicação externa. Aprovação editorial não publica automaticamente.')
        for provider in PROVIDERS:
            status = connection_status(provider)
            label = 'Não configurado' if status['state'] == 'NOT_CONFIGURED' else 'Configuração presente; conta não verificada'
            st.write(f"**{status['label']}** · {label}")
            st.caption(status['requirements'])
            if status['missing']:
                st.caption('Configuração ausente: ' + ', '.join(status['missing']))
        choices = [(job['id'], i, clip) for job in jobs if job.get('editorial_protocol') == 2
                   for i, clip in enumerate(job.get('candidates', [])) if clip.get('artifact_id')]
        if not choices:
            st.info('Após renderizar e aprovar um candidato na revisão v2, prepare o rascunho aqui.')
            return
        selected = st.selectbox('Candidato para preflight', range(len(choices)),
                                format_func=lambda i: f"{choices[i][0][:8]} · candidato {choices[i][1]+1}", key='publishing_candidate')
        jid, index, clip = choices[selected]
        provider = st.selectbox('Destino do rascunho', list(PROVIDERS), format_func=lambda p: PROVIDERS[p]['label'], key='publishing_provider')
        title = st.text_input('Título de publicação', value=str(clip.get('title') or '')[:100], max_chars=100, key=f'publishing_title_{jid}_{index}')
        description = st.text_area('Descrição / legenda', max_chars=2200, key=f'publishing_description_{jid}_{index}')
        if st.button('Validar e salvar rascunho local', key='publishing_dry_run'):
            try:
                result = queue_dry_run(jid, clip['candidate_id'], provider, title=title, description=description)
                st.success('Rascunho local salvo. Nenhum conteúdo foi enviado.')
                st.json(result)
            except (ValueError, service.Conflict, OSError):
                st.error('Preflight recusado: confirme aprovação integral v2, QC, título e integridade do render atual. Rascunho não criado.')
