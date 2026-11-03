from __future__ import annotations
import os
import shutil
import uuid
from pathlib import Path
import streamlit as st
from app.store import INPUT, OUTPUT, all_jobs, load, new_job, rconn, save
from app.youtube import normalize_youtube_url
from app.dashboard_health import render_doctor, render_job_ai
from app.asset_library import register_asset
from app.edit_render import read_assets

st.set_page_config(page_title="GTA VI — Clip Factory MVP", page_icon="🎬", layout="wide")
st.title("🎬 Content Factory — Creator Clips")
st.caption("v4: vídeo autorizado → Whisper por palavra → Qwen Editor → timeline → FFmpeg/Remotion → revisão humana. Sem postagem automática.")
st.warning("Uso privado: a interface deve ficar acessível apenas via localhost, SSH tunnel ou VPN. Não exponha a porta 8501 publicamente.")
with st.expander("Adicionar um vídeo autorizado", expanded=True):
    # Outside st.form so changing the input source causes an immediate Streamlit rerun.
    source_type = st.radio("Origem", ["Upload local", "URL do YouTube"], horizontal=True, key="source_type")
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
                    if source_type == "URL do YouTube":
                        canonical = normalize_youtube_url(youtube_url)
                        job = new_job(None, canonical, creator.strip(), license_note.strip(), source_url=canonical, platform_permission=True)
                    else:
                        suffix = Path(uploaded.name).suffix.lower()
                        temp = INPUT / f"{uuid.uuid4().hex}{suffix}"
                        with temp.open("wb") as f:
                            shutil.copyfileobj(uploaded, f)
                        job = new_job(temp, uploaded.name, creator.strip(), license_note.strip())
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    try:
                        rconn().lpush("clips:queue", job["id"])
                        st.success(f"Job {job['id']} enfileirado. Atualize a página para acompanhar.")
                    except Exception as ex:
                        job["status"] = "FAILED"
                        job["error"] = f"Queue unavailable: {ex}"
                        save(job)
                        st.error(job["error"])

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
.ai-dot {display:inline-block; width:12px; height:12px; background:#18ac81; border-radius:50%; animation:ai-pulse 1.1s ease-in-out infinite; margin-right:8px;vertical-align:middle}
</style>""", unsafe_allow_html=True)

@st.fragment(run_every="4s")
def doctor_fragment():
    render_doctor()

with st.expander("🩺 Doctor / AI Health Check", expanded=True):
    doctor_fragment()

st.subheader("Jobs e aprovação")
jobs = all_jobs()
if not jobs:
    st.info("Nenhum job. Envie um vídeo autorizado para testar.")
else:
    options = {f"{j['original_name']} · {j['creator']} · {j['status']} · {j['id'][:8]}": j["id"] for j in reversed(jobs)}
    choice = st.selectbox("Selecione um job", list(options))
    job = load(options[choice])
    st.write(f"**Status:** `{job['status']}`  |  **Criador:** {job['creator']}")
    st.caption(f"Licença/registro: {job['license_note']}")
    render_job_ai(job)
    if job.get("error"):
        st.error(job["error"])
    if job["status"] in ("NEEDS_REVIEW", "APPROVED", "REJECTED"):
        selected = []
        for idx, clip in enumerate(job["candidates"]):
            file = Path(clip.get("file", ""))
            st.markdown(f"#### Candidato {idx+1} — {clip['start']:.1f}s a {clip['end']:.1f}s")
            st.caption(f"Pontuação: {clip['score']} · {clip['reason']}")
            if clip.get("ai_reason"):
                st.info("Análise local: " + clip["ai_reason"])
            st.caption(f"Direção: {clip.get('director_used', 'legado')} · Render: {clip.get('renderer_used', 'legado')} · Palavras sincronizadas: {clip.get('word_count', 'n/d')}")
            st.write(clip["text"])
            timeline_path = Path(clip.get("timeline_file") or "/not-found")
            if timeline_path.is_file():
                with timeline_path.open("rb") as timeline_handle:
                    st.download_button("Baixar timeline JSON", timeline_handle, file_name=timeline_path.name, mime="application/json", key=f"timeline_{job['id']}_{idx}")
            if file.is_file():
                st.video(str(file))
                with file.open("rb") as f:
                    st.download_button(f"Baixar candidato {idx+1}", f, file_name=file.name, mime="video/mp4", key=f"download_{job['id']}_{idx}")
            if st.checkbox(f"Aprovar candidato {idx+1}", value=idx in job.get("approved", []), key=f"approve_{job['id']}_{idx}"):
                selected.append(idx)
        col1, col2 = st.columns(2)
        if col1.button("Salvar aprovação", type="primary", disabled=job["status"] not in ("NEEDS_REVIEW", "APPROVED", "REJECTED")):
            job["approved"] = selected
            job["status"] = "APPROVED" if selected else "REJECTED"
            save(job)
            st.success("Decisão registrada. Nenhuma postagem é realizada.")
            st.rerun()
        if col2.button("Rejeitar todos"):
            job["approved"] = []
            job["status"] = "REJECTED"
            save(job)
            st.rerun()
    elif job["status"] in ("QUEUED", "DOWNLOADING", "TRANSCRIBING", "DIRECTING", "RENDERING"):
        st.info("Worker em processamento. O painel Doctor atualiza a cada 4 segundos; clique abaixo para atualizar os detalhes do job.")
    if st.button("Atualizar status"):
        st.rerun()
