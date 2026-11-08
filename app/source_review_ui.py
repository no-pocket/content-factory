"""Source comparison workspace; rendered separately from the single-job workspace."""
from __future__ import annotations
import uuid
from . import store
from .source_review import IDENTITY, get_group, list_groups, select_finals
from .editorial_ui import render_v2_review, LABELS
from .service import Conflict


def _model_label(model):
    fallback = any('fallback' in str(model.get(key) or '').lower() for key in ('engine','ranker_used','director_used'))
    parts = [model['label'] + (' (solicitado)' if fallback else '')]
    if model.get('engine') and model['engine']!=model['label']:
        parts.append('seleção: ' + model['engine'])
    if model.get('backend') and model['backend']!=model.get('engine'):
        parts.append('backend: ' + model['backend'])
    if model.get('director_used'):
        parts.append('direção: ' + model['director_used'])
    return ' / '.join(parts)


def render_source_review(st):
    st.subheader('Comparar cortes da mesma fonte')
    st.caption('Modelos e jobs visíveis desde o início. Escolha nenhum, um ou vários finais; a seleção não substitui a aprovação editorial.')
    groups = list_groups()
    if not groups:
        st.info('Nenhuma fonte disponível.');return
    options = {g['group_id']:g for g in groups}
    requested = st.query_params.get('group')
    if requested and requested not in options:
        try:
            resolved = get_group(requested)['group_id']
            requested = resolved
        except ValueError:
            st.warning('Grupo solicitado não encontrado.')
    labels = {gid:(g['jobs'][0].get('original_name') or g['jobs'][0]['id'][:8]) + ' — ' + ', '.join(dict.fromkeys(_model_label(j['model']) for j in g['jobs'])) for gid,g in options.items()}
    gid = st.selectbox('Fonte e modelos',list(options),index=list(options).index(requested) if requested in options else 0,format_func=labels.__getitem__,key='source_review_group')
    group = get_group(gid)
    if group['reconciliation_required']:
        st.warning('Fontes antes separadas foram unidas por proveniência confirmada. As seleções anteriores estão preservadas no histórico; nenhum final é considerado atual até você escolher e salvar uma nova seleção para a fonte reunida.')
    revision_key = 'source_displayed_revision_' + gid
    if revision_key not in st.session_state:
        st.session_state[revision_key] = group['revision']
    changed = st.session_state[revision_key] != group['revision']
    if changed:
        st.warning('A comparação mudou. Confira as avaliações e os renders atuais antes de salvar suas escolhas. Seu rascunho foi mantido para os mesmos artefatos.')
        if st.button('Atualizar comparação e manter escolhas',key='source_refresh_'+gid):
            st.session_state[revision_key] = group['revision']
            st.rerun()
    st.caption('Identidade da fonte: ' + gid)
    for job in group['jobs']:
        st.caption(f"{_model_label(job['model'])} · job {job['id'][:8]} · {job['status']}")
    selected = []
    for row in group['candidates']:
        prefix = 'source_' + gid + '_' + row['job_id'] + '_' + row['candidate_id'] + '_' + str(row['artifact_id'])
        st.markdown(f"#### Job {row['job_id'][:8]} · candidato {row['original_index']+1} · {row['start']}s a {row['end']}s")
        st.caption(f"{_model_label(row['model'])} · versão {row['candidate_version']} · render {row['render_revision']}")
        st.caption('Decisão salva: ' + LABELS.get(row.get('normalized_decision'),'Legado não confirmado') + ' · ' + ('Pronto editorialmente' if row['release_ready'] else 'Pendente de aprovação/QC/ajustes'))
        if row['overlaps']:
            st.caption('Sobreposições na fonte: ' + ' · '.join(f"{o['job_id'][:8]} / {o['candidate_id']} ({o['seconds']:.1f}s)" for o in row['overlaps']))
        media, review = st.columns(2)
        job = store.load(row['job_id']);clip = job['candidates'][row['original_index']]
        with media:
            if row['artifact_intact']:
                from .artifacts import artifact_manifest
                manifest = artifact_manifest(job,row['original_index'],presentation_cache=True)
                kind = st.radio('Reprodução',['Prévia WebM','MP4 mestre'],horizontal=True,key=prefix+'media')
                info = manifest['files']['webm' if kind=='Prévia WebM' else 'mp4']
                path = store.OUTPUT / job['id'] / info['path']
                st.video(str(path),format='video/webm' if kind=='Prévia WebM' else 'video/mp4')
            else:
                st.warning('Render ausente ou alterado; não pode ser selecionado como final atual.')
            if st.checkbox('Selecionar como final',value=row['selected_current'],disabled=not row['selectable'],key=prefix+'selected') and row['selectable']:
                selected.append({k:row[k] for k in IDENTITY})
            st.write(row.get('text',''))
        with review:
            if job.get('editorial_protocol')==2:
                render_v2_review(st,job,row['original_index'],row)
            else:
                st.write(row.get('comment_raw',''))
                st.caption('Use a opção Job individual para revisar candidatos legados.')
    comment = st.text_area('Comentário da seleção final',key='source_final_comment_'+gid)
    if st.button('Salvar seleção de finais (inclusive nenhum)',key='source_final_save_'+gid,disabled=changed):
        try:
            select_finals(gid,{'request_id':str(uuid.uuid4()),'expected_revision':st.session_state[revision_key],'selected':selected,'comment_raw':comment})
            del st.session_state[revision_key]
            st.success('Seleção final salva. Aprovações e histórico editorial preservados.')
            st.rerun()
        except (ValueError,Conflict) as exc:
            st.error(str(exc))
    if group['selection_history']:
        with st.expander('Histórico das seleções finais'):
            st.json(group['selection_history'])
