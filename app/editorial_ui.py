"""Candidate filters and the Streamlit v2 review panel."""
from __future__ import annotations

import uuid

LABELS = {'PENDING': 'Pendente', 'APPROVED': 'Aprovado',
          'APPROVED_WITH_ADJUSTMENTS': 'Aprovado com ajustes', 'REJECTED': 'Recusado',
          'UNCONFIRMED_LEGACY': 'Legado — condição não confirmada'}
DIMENSION_LABELS = {'relevance': 'Relevância', 'hook': 'Gancho', 'context': 'Contexto independente',
                    'narrative': 'Desenvolvimento', 'proof': 'Prova / demonstração', 'closure': 'Fechamento',
                    'framing': 'Enquadramento', 'captions': 'Legendas', 'editing': 'Edição',
                    'technical_quality': 'Qualidade técnica percebida'}


def filter_candidates(rows: list[dict], filters: dict) -> list[dict]:
    decision, technical = filters.get('decision'), filters.get('technical_state')
    def matches(row):
        actual = row.get('normalized_decision')
        if decision == 'UNCONFIRMED_LEGACY':
            if row.get('qualification_status') != decision:
                return False
        elif decision and actual != decision:
            # Rejections remain discoverable within approved legacy jobs.
            if not (actual is None and decision == 'REJECTED' and row.get('legacy_decision') == 'REJECTED'):
                return False
        if technical and row.get('technical_state') != technical:
            return False
        if filters.get('open_edits') and not any(e['status'] == 'OPEN' for e in row.get('edit_requests', [])):
            return False
        return True
    return [row for row in rows if matches(row)]


def render_v2_review(st, job: dict, index: int, row: dict) -> None:
    from .editorial_contracts import REASONS
    from .service import review_candidate_v2, Conflict
    cid = row['candidate_id']
    # Versioned draft keys prevent accidental reuse of a comment on another render.
    prefix = f"v2_{job['id']}_{cid}_{row['artifact_id']}_"
    revision_key = prefix+'displayed_revision'
    if revision_key not in st.session_state:
        st.session_state[revision_key] = job.get('editorial_revision',0)
    def clear_draft():
        for key in list(st.session_state):
            if key.startswith(prefix):
                del st.session_state[key]
    if st.session_state[revision_key] != job.get('editorial_revision',0):
        st.warning('Existe uma avaliação mais recente. Seu rascunho ainda usa a revisão que você abriu.')
        if st.button('Recarregar avaliação atual e descartar este rascunho',key=prefix+'reload'):
            clear_draft()
            st.rerun()
    old = row.get('current_event') or {}
    st.caption(f"Candidato {index+1} · versão {row['candidate_version']} · render {row['render_revision']}")
    decision = row['normalized_decision']
    st.info('Decisão salva: ' + LABELS.get(decision, LABELS['UNCONFIRMED_LEGACY']))
    comment = st.text_area('Comentário / motivo', value=old.get('comment_raw', ''),
                           max_chars=4000, key=prefix+'comment')
    with st.expander('Motivos, notas e ajustes (opcional)'):
        reasons = st.multiselect('Motivos', REASONS, default=[r['code'] for r in old.get('reasons', [])], key=prefix+'reasons')
        severity = st.selectbox('Severidade dos motivos selecionados', [None, 'MINOR', 'MAJOR', 'CRITICAL'],
                                 format_func=lambda value: value or 'Não informada', key=prefix+'severity')
        dimensions = {key: st.number_input(label+' (1–5)', min_value=1, max_value=5,
                       value=old.get('dimensions', {}).get(key), key=prefix+key)
                      for key, label in DIMENSION_LABELS.items()}
        grade = st.number_input('Grau de conteúdo (0–3)', min_value=0, max_value=3,
                                 value=old.get('content_grade'), key=prefix+'grade')
        domain = st.selectbox('Domínio da recusa', ['UNSPECIFIED', 'EDITORIAL', 'TECHNICAL', 'ADMINISTRATIVE', 'MIXED'], key=prefix+'domain')
        adjustment = st.text_area('Pedido de edição', max_chars=4000, key=prefix+'adjustment')
        edit_type = st.selectbox('Tipo de ajuste', ['BOUNDARY_END', 'BOUNDARY_START', 'FRAMING', 'CAPTIONS', 'TITLE', 'EDITING', 'OTHER'], key=prefix+'edit_type')
        existing_edits = old.get('edit_requests',[])
        open_edits = {e['edit_id']: e for e in existing_edits if e['status']=='OPEN'}
        resolved = st.multiselect('Pedidos resolvidos nesta revisão',list(open_edits),
            format_func=lambda ident: open_edits[ident]['type']+': '+open_edits[ident]['comment'],key=prefix+'resolved')
    ready = row['artifact_intact'] and row['technical_state'] in {'VALID', 'WARNING'}
    clean, adjust, reject = st.columns(3)
    clean_clicked = clean.button('Aprovar', key=prefix+'approve', disabled=not ready)
    adjust_clicked = adjust.button('Aprovar com ajustes', key=prefix+'adjust', disabled=not ready)
    reject_clicked = reject.button('Recusar', key=prefix+'reject')
    action = 'APPROVED' if clean_clicked else 'APPROVED_WITH_ADJUSTMENTS' if adjust_clicked else 'REJECTED' if reject_clicked else None
    if action:
        edits = [{**edit,'status':'RESOLVED' if edit['edit_id'] in resolved else edit['status']} for edit in existing_edits]
        if adjustment.strip():
            edits.append({'edit_id':str(uuid.uuid4()),'type':edit_type,'status':'OPEN','severity':severity,'comment':adjustment})
        request = {'request_id': str(uuid.uuid4()), 'expected_editorial_revision': st.session_state[revision_key],
                   'expected_artifact_id': row['artifact_id'], 'decision': action, 'comment_raw': comment,
                   'rejection_domain': domain if action == 'REJECTED' else None,
                   'dimensions': dimensions, 'content_grade': grade,
                   'reasons': [{'code': code, 'severity': severity, 'confirmed_by': 'human'} for code in reasons],
                   'edit_requests': edits}
        try:
            review_candidate_v2(job['id'], cid, request)
            st.session_state['review_feedback'] = 'Avaliação salva para este render. '+LABELS[action]+'.'
            clear_draft()
            st.rerun()
        except Conflict:
            st.error('A revisão ou o render mudou. Recarregue o job e confira o vídeo. Seu comentário permanece no rascunho deste render.')
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
    if row['history']:
        with st.expander('Histórico de avaliações deste candidato'):
            st.json(row['history'])
