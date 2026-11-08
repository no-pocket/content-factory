from __future__ import annotations
import os
import shutil
import uuid
import json
from pathlib import Path
import streamlit as st
from app.store import INPUT, OUTPUT, all_jobs, load, new_job, rconn, save
from app.youtube import normalize_youtube_url
from app.dashboard_health import render_doctor, render_job_ai
from app.version import VERSION
from app.asset_library import register_asset
from app.edit_render import read_assets, browser_preview
from app.ui_settings import render_settings_controls, render_duration_mode_control
from app.service import create_job, review_job, retry_candidate, retry_enqueue, verify_existing, review_candidate, reject_job
from app.editorial import DIMENSIONS, summarize, current_decisions
from app.quality import normalize_qc
from app.service import get_editorial_view
from app.editorial_ui import filter_candidates, render_v2_review, LABELS as REVIEW_LABELS
from app.editorial import summarize_v2

st.set_page_config(page_title="GTA VI — Clip Factory MVP", page_icon="🎬", layout="wide")
st.title("🎬 Content Factory — Creator Clips")
st.caption(f"Versão {VERSION}")
if st.session_state.get("review_feedback"):
    st.success(st.session_state.pop("review_feedback"))
st.caption("v4: vídeo autorizado → Whisper por palavra → Qwen Editor → timeline → FFmpeg/Remotion → revisão humana. Sem postagem automática.")
st.warning("Uso privado: a interface deve ficar acessível apenas via localhost, SSH tunnel ou VPN. Não exponha a porta 8501 publicamente.")
st.caption('Perfil inicial de novos jobs: Qwen na GPU K4200 + Remotion + alta fidelidade. CPU e outros ajustes continuam disponíveis no formulário.')
with st.expander("Adicionar um vídeo autorizado", expanded=True):
    # Outside st.form so changing the input source causes an immediate Streamlit rerun.
    source_type = st.radio("Origem", ["Upload local", "URL do YouTube"], horizontal=True, key="source_type")
    duration_mode = render_duration_mode_control(st, key_prefix='production_v2_')
    with st.form("ingest", clear_on_submit=True):
        uploaded = st.file_uploader("Vídeo local (MP4/MOV/MKV)", type=["mp4", "mov", "mkv"]) if source_type == "Upload local" else None
        youtube_url = st.text_input("URL de um vídeo do YouTube (sem playlist)") if source_type == "URL do YouTube" else ""
        if source_type == "URL do YouTube":
            st.caption("O download direto exige autorização do titular e autorização aplicável do YouTube. O recurso fica desabilitado por padrão no .env.")
            platform_permission = st.checkbox("Confirmo que o download por este método também é autorizado pelo YouTube, além do titular do conteúdo")
        else:
            platform_permission = False
        creator = st.text_input("Criador / canal", placeholder="Nome do criador")
        license_note = st.text_area("Comprovação ou referência da autorização", placeholder="URL/ID da licença, acordo escrito, alcance comercial e permissão para editar/cortar")
        with st.expander('Ajustes de processamento'):
            st.caption('Estes valores são salvos por job e também podem ser enviados pela entrada JSON.')
            processing_settings = render_settings_controls(st, preferred={'llm_backend':'kepler_gpu'}, key_prefix='production_v2_', duration_mode=duration_mode)
            assembly_json = st.text_area('Plano de montagem opcional (JSON avançado)', max_chars=16000,
                                         help='Uma fonte, intervalos source_in/source_out e propósito por trecho. Requer montagem multitrecho e protocolo editorial 2.')
        permitted = st.checkbox("Confirmo que possuo permissão para editar este vídeo e gerar cortes (e para os usos posteriores pretendidos)")
        submitted = st.form_submit_button("Criar job de cortes", type="primary")
        if submitted:
            if not (creator.strip() and license_note.strip() and permitted):
                st.error("Informe criador, evidência de autorização e confirme as permissões.")
            elif source_type == "Upload local" and not uploaded:
                st.error("Selecione um arquivo de vídeo.")
            elif source_type == "URL do YouTube" and not platform_permission:
                st.error("Para ingestão por URL é necessária a autorização aplicável da plataforma.")
            else:
                try:
                    payload = {'creator': creator, 'license_note': license_note,
                               'rights_confirmed': permitted, 'platform_permission': platform_permission,
                               'settings': processing_settings}
                    if source_type == "URL do YouTube":
                        payload['source_url'] = youtube_url
                    if assembly_json.strip():
                        payload['assembly_plan'] = json.loads(assembly_json)
                    job = create_job(payload, upload=uploaded,
                                     filename=uploaded.name if uploaded else None)
                    st.success(f"Job {job['id']} enfileirado. Atualize a página para acompanhar.")
                except (ValueError, PermissionError, RuntimeError) as exc:
                    st.error(str(exc))

with st.expander("🎮 Biblioteca de gameplay / B-roll autorizado"):
    existing_assets = read_assets()
    st.caption(f"{len(existing_assets)} assets cadastrados. O diretor usa apenas arquivos com licença registrada.")
    if existing_assets:
        st.dataframe([{"ID": asset_id, "Descrição": meta["description"], "Duração": meta["duration"]} for asset_id, meta in existing_assets.items()], use_container_width=True, hide_index=True)
    with st.form("add_broll"):
        footage = st.file_uploader("Arquivo de gameplay autorizado", type=["mp4", "mov", "mkv", "webm"], key="asset_upload")
        description = st.text_input("Descrição do que aparece (ex.: carros dirigindo em Vice City)")
        rights = st.text_area("Referência e escopo da autorização")
        license_ok = st.checkbox("Confirmo permissão para edição e uso deste material no projeto")
        if st.form_submit_button("Adicionar à biblioteca"):
            if not footage or not description.strip() or not rights.strip() or not license_ok:
                st.error("Informe arquivo, descrição e autorização.")
            else:
                try:
                    record = register_asset(footage, footage.name, description, rights)
                    st.success(f"Asset {record['asset_id']} adicionado. Novos jobs poderão utilizá-lo.")
                except Exception as exc:
                    st.error(str(exc))

st.markdown("""<style>
@keyframes ai-pulse { 0%,100% {opacity:.25; transform:scale(.85)} 50% {opacity:1; transform:scale(1.15)} }
video {width:min(100%,340px) !important; height:auto !important; max-height:605px; object-fit:contain}
.ai-dot {display:inline-block; width:12px; height:12px; background:#18ac81; border-radius:50%; animation:ai-pulse 1.1s ease-in-out infinite; margin-right:8px;vertical-align:middle}
</style>""", unsafe_allow_html=True)

@st.fragment(run_every="4s")
def doctor_fragment():
    render_doctor()

with st.expander("🩺 Doctor / AI Health Check", expanded=True):
    doctor_fragment()

from app.source_review_ui import render_source_review
# Existing open review sessions predate the workspace selector. Keep rendering
# their job and widgets so Streamlit does not clean up unsaved review drafts.
individual_default = bool(st.query_params.get('job') or
                          ('selected_job' in st.session_state and not st.query_params.get('group')))
workspace = st.radio('Área editorial', ['Comparar fontes e escolher finais', 'Job individual'],
                     index=1 if individual_default else 0, horizontal=True, key='editorial_workspace')
if workspace == 'Comparar fontes e escolher finais':
    render_source_review(st)
    st.stop()
st.subheader("Jobs e aprovação")
jobs = all_jobs()
if not jobs:
    st.info("Nenhum job. Envie um vídeo autorizado para testar.")
else:
    candidate_filter = st.selectbox('Filtrar candidatos', [None, 'PENDING', 'APPROVED', 'APPROVED_WITH_ADJUSTMENTS', 'REJECTED', 'UNCONFIRMED_LEGACY'],
                                     format_func=lambda value: REVIEW_LABELS.get(value, 'Todos'), key='candidate_filter')
    if candidate_filter:
        jobs = [j for j in jobs if filter_candidates(get_editorial_view(j)['candidates'], {'decision': candidate_filter})]
    if not jobs:
        st.info('Nenhum candidato corresponde ao filtro.')
        st.stop()
    grouped = {'Para revisar':[j for j in jobs if j['status'] not in {'APPROVED','REJECTED'}],
               'Aprovados':[j for j in jobs if j['status']=='APPROVED'],
               'Recusados':[j for j in jobs if j['status']=='REJECTED']}
    view = st.selectbox('Exibir jobs', ['Todos'] + [k for k,v in grouped.items() if v], key='job_filter')
    jobs = grouped.get(view, jobs)
    def job_label(value):
        status = 'Revisão individual' if value['status'] in {'APPROVED', 'REJECTED', 'NEEDS_REVIEW'} else value['status']
        return f"{value['original_name']} · {value['creator']} · {status} · {value['id'][:8]}"
    options = {j['id']: job_label(j) for j in reversed(jobs)}
    requested_job = st.query_params.get('job')
    choice = st.selectbox("Selecione um job", list(options), index=list(options).index(requested_job) if requested_job in options else 0,
                          format_func=options.__getitem__, key='selected_job')
    job = load(choice)
    st.write(f"**{job_label(job)}**")
    st.caption(f"Licença/registro: {job['license_note']}")
    if job.get('language'):
        st.caption(f"Idioma detectado na transcrição: {job['language']} · fala original preservada")
    if job.get('comparison'):
        comparison=job['comparison']
        st.info(f"Comparação editorial · {comparison['label']} · decisões do motor sem complemento heurístico · aguardando sua avaliação")
    if job.get('settings'):
        with st.expander('Ajustes salvos deste job'):
            st.json(job['settings'])
    render_job_ai(job)
    if job.get('ai_events'):
        with st.expander('Histórico da seleção e fallbacks'):
            st.json(job['ai_events'])
    if job.get("error"):
        st.error(job["error"])
    if job['status'] in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'FAILED', 'APPROVED', 'REJECTED'} and job.get('candidates'):
        if st.button('Verificar arquivos existentes (sem renderizar)'):
            with st.spinner('Decodificando MP4 e WebM completos…'):
                try:
                    verify_existing(job['id'])
                    st.rerun()
                except (ValueError, RuntimeError) as exc:
                    st.error(str(exc))
    if job["status"] in ("NEEDS_REVIEW", "PARTIAL_FAILED", "FAILED", "APPROVED", "REJECTED"):
        decisions = []
        previous = current_decisions(job)
        editorial_view = get_editorial_view(job)
        counts = editorial_view['counts']
        st.caption(' · '.join(f'{REVIEW_LABELS[key]}: {count}' for key, count in counts.items() if count))
        visible = {r['original_index']: r for r in filter_candidates(editorial_view['candidates'], {'decision': candidate_filter})}
        for idx, clip in enumerate(job["candidates"]):
            if idx not in visible:
                continue
            row = visible[idx]
            file = Path(clip.get("file", ""))
            assembly = clip.get('assembly')
            if assembly:
                st.markdown(f"#### Candidato {idx+1} — montagem de {assembly['duration']:.1f}s · {len(assembly['segments'])} trechos")
                with st.expander('Trechos usados da fonte'):
                    for piece in assembly['segments']:
                        st.write(f"{piece['source_in']:.2f}s a {piece['source_out']:.2f}s → a partir de {piece['output_start']:.2f}s na montagem")
            else:
                st.markdown(f"#### Candidato {idx+1} — {clip['start']:.1f}s a {clip['end']:.1f}s")
            if job.get('comparison'):
                st.caption(f"Ordem escolhida pelo motor: {clip.get('selection_rank','n/d')} · {clip.get('reason','')}")
            else:
                st.caption(f"Sinal heurístico: {clip.get('score', 'n/d')} · {clip.get('reason', '')}")
            if clip.get("ai_reason"):
                st.info("Análise local: " + clip["ai_reason"])
            if clip.get('story_assessment', {}).get('quality_uncertain'):
                st.caption('Avaliação automática incerta: confira relevância, demonstração e fechamento.')
                with st.expander('Sinais editoriais automáticos'):
                    st.json(clip['story_assessment'])
            st.caption(f"Direção: {clip.get('director_used', 'legado')} · Render: {clip.get('renderer_used', 'legado')} · Palavras sincronizadas: {clip.get('word_count', 'n/d')}")
            with st.expander("Transcrição e informações do corte"):
                st.write(clip.get('text', ''))
            state = clip.get('state', 'UNVERIFIED')
            st.caption(f"QC: {state} · Tentativas: {clip.get('attempts', 0)}")
            if clip.get('qc'):
                with st.expander(f"Diagnóstico técnico {idx+1}"):
                    st.json(clip['qc'])
            media_panel, review_panel = st.columns([1, 1.5], gap='large')
            with media_panel:
                if state in {'VALID', 'WARNING'} and file.is_file():
                    quality_view = st.radio('Reprodução', ['Prévia WebM', 'MP4 mestre'], horizontal=True,
                                            key=f"view_{job['id']}_{idx}")
                    preview, mime = browser_preview(file) if quality_view == 'Prévia WebM' else (file, 'video/mp4')
                    st.video(str(preview), format=mime)
                    st.caption('Prévia compacta. Use MP4 mestre para conferir a qualidade de imagem.')
                    with file.open('rb') as handle:
                        st.download_button(f'Baixar MP4 {idx+1}', handle, file_name=file.name, mime='video/mp4', key=f"download_{job['id']}_{idx}")
                else:
                    st.warning('Arquivo não verificado ou com falha técnica. Pode ser recusado com comentário.')
                    if st.button(f'Tentar novamente candidato {idx+1}', key=f"retry_{job['id']}_{idx}",
                                 disabled=state != 'FAILED' or clip.get('attempts', 0) >= normalize_qc(job.get('qc_settings'))['max_attempts']):
                        try:
                            retry_candidate(job['id'], idx)
                            st.rerun()
                        except (ValueError, RuntimeError) as exc:
                            st.error(str(exc))
                if clip.get('renderer_used', '').startswith('ffmpeg'):
                    st.warning('Edição simplificada FFmpeg: este arquivo não tem as animações e zooms do perfil Remotion aprovado.')
                timeline_path = Path(clip.get('timeline_file') or '/not-found')
                if timeline_path.is_file():
                    with st.expander('Timeline do corte'):
                        with timeline_path.open('rb') as timeline_handle:
                            st.download_button('Baixar timeline JSON', timeline_handle, file_name=timeline_path.name,
                                               mime='application/json', key=f"timeline_{job['id']}_{idx}")
            with review_panel:
                if job.get('editorial_protocol') == 2:
                    render_v2_review(st, job, idx, row)
                    continue
                if row['legacy_decision']:
                    st.info(('Aprovado' if row['legacy_decision'] == 'APPROVED' else 'Recusado')+' — condição não confirmada (legado)')
                old = previous.get(idx, {})
                reason = st.text_area('Comentário / motivo', value=old.get('reason', ''), key=f"reason_{job['id']}_{idx}")
                with st.expander('Notas e retrabalho (opcional)'):
                    labels = {'hook': 'Gancho', 'context': 'Contexto', 'closure': 'Fechamento', 'captions': 'Legendas'}
                    ratings = {key: st.number_input(labels[key] + ' (1–5)', min_value=1, max_value=5,
                               value=old.get(key), key=f"{key}_{job['id']}_{idx}") for key in DIMENSIONS}
                    rework = st.checkbox('Requer retrabalho', value=old.get('rework', False), key=f"rework_{job['id']}_{idx}")
                    adjustments = st.text_area('Ajustes necessários', value=old.get('adjustments', ''), key=f"adjustments_{job['id']}_{idx}")
                approve_column, reject_column = st.columns(2)
                approve_clicked = approve_column.button(f'Aprovar candidato {idx+1}', key=f"approve_{job['id']}_{idx}", disabled=state not in {'VALID','WARNING'})
                reject_clicked = reject_column.button(f'Recusar candidato {idx+1}', key=f"reject_{job['id']}_{idx}")
                if approve_clicked or reject_clicked:
                    try:
                        review_candidate(job['id'], idx, 'APPROVED' if approve_clicked else 'REJECTED', reason,
                                         expected_revision=len(job.get('decision_history', [])), ratings=ratings,
                                         rework=rework, adjustments=adjustments)
                        st.session_state['review_feedback'] = f'Candidato {idx+1} ' + ('aprovado' if approve_clicked else 'recusado') + ' com comentário.'
                        st.rerun()
                    except (ValueError, RuntimeError) as exc:
                        st.error(str(exc))
                if old:
                    st.caption('Decisão registrada: ' + ('Aprovado' if old['decision']=='APPROVED' else 'Recusado'))
        st.caption(f"Revisões preservadas: {len(job.get('decision_history', []))}")
        with st.expander('Recusar o job inteiro (protocolo legado)'):
            rejection_reason = st.text_area('Comentário para todos os candidatos', key=f"reject_job_reason_{job['id']}")
            if st.button('Recusar todos os candidatos deste job', key=f"reject_job_{job['id']}", disabled=job.get('editorial_protocol') == 2):
                try:
                    reject_job(job['id'], rejection_reason)
                    st.session_state['review_feedback'] = 'Job recusado; arquivos e histórico preservados.'
                    st.rerun()
                except (ValueError, RuntimeError) as exc:
                    st.error(str(exc))
    elif job['status'] == 'QUEUE_FAILED':
        if st.button('Tentar enfileirar novamente'):
            try:
                retry_enqueue(job['id'])
                st.rerun()
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
    elif job["status"] in ("QUEUED", "DOWNLOADING", "TRANSCRIBING", "DIRECTING", "RENDERING"):
        st.info("Worker em processamento. O painel Doctor atualiza a cada 4 segundos; clique abaixo para atualizar os detalhes do job.")
    if st.button("Atualizar status"):
        st.rerun()

with st.expander('Métricas editoriais e comparação de configurações'):
    if st.button('Calcular métricas agora',key='load_editorial_metrics',
                   help='Calcula a cobertura e métricas de todos os jobs sob demanda, sem atrasar cada comentário.'):
        metric_jobs=all_jobs()
        st.session_state['editorial_metrics_snapshot']=(summarize_v2(metric_jobs),summarize(metric_jobs))
    if 'editorial_metrics_snapshot' in st.session_state:
        for metric in st.session_state['editorial_metrics_snapshot']:st.json(metric)
    st.caption('Sem atualização automática da seleção. Compare os mesmos vídeos antes e depois e registre avaliações reais.')
    st.caption('ML: avaliações viram eventos versionados; não há treino nem promoção automática. '
               'O alvo proposto usa grau de conteúdo ≥ 2; notas das dimensões ainda não têm pesos treinados. '
               'O treino exige dataset congelado, 150 candidatos elegíveis de 50 famílias, '
               '30 positivos/30 negativos, cobertura PT/EN, holdout e aprovação explícita.')

from app.publishing import render_publishing_panel
render_publishing_panel(st,jobs)
