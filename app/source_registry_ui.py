"""Local owner administration for authorized channel records."""
from __future__ import annotations
from .source_registry import list_sources, upsert_source


def render_source_registry(st):
    with st.expander('Fontes autorizadas — canais cadastrados'):
        st.caption('Canais cadastrados são permissões de ingestão. Grupos editoriais comparam vídeos já processados. Nenhum cadastro inicia jobs ou monitoramento.')
        records = list_sources()
        selected = st.selectbox('Editar fonte', ['Novo cadastro'] + [r['channel_id'] for r in records],
                                key='registry_selection')
        current = next((r for r in records if r['channel_id'] == selected), {})
        # Separate widget instances when changing source, without touching editorial drafts.
        prefix = 'registry_' if not current else 'registry_' + selected + '_'
        revision_key = prefix + 'loaded_revision'
        st.session_state.setdefault(revision_key, current.get('revision', 0))
        if st.button('Atualizar cadastro e descartar alterações desta fonte', key=prefix+'refresh'):
            for key in list(st.session_state):
                if key.startswith(prefix) and key != 'registry_selection':
                    del st.session_state[key]
            st.rerun()
        with st.form('registry_form_' + selected):
            channel_id = st.text_input('ID canônico do canal (UC + 22 caracteres)', value=current.get('channel_id', ''), key=prefix+'channel_id', disabled=bool(current))
            name = st.text_input('Nome do canal', value=current.get('name', ''), key=prefix+'name')
            status = st.selectbox('Situação da autorização', ['pending', 'active', 'disabled'],
                                  index=['pending', 'active', 'disabled'].index(current.get('status', 'pending')), key=prefix+'status')
            reference = st.text_area('Referência e escopo da autorização do titular', value=current.get('authorization_reference', ''), key=prefix+'reference')
            rights = st.checkbox('Confirmo permissão do titular para editar e gerar cortes', value=current.get('rights_confirmed', False), key=prefix+'rights')
            platform = st.checkbox('Confirmo autorização aplicável da plataforma para download', value=current.get('platform_permission', False), key=prefix+'platform')
            languages = st.text_input('Idiomas permitidos (separados por vírgula)', value=','.join(current.get('allowed_languages', [])), key=prefix+'languages')
            kinds = st.multiselect('Tipos permitidos', ['video', 'short', 'live_archive'], default=current.get('allowed_video_kinds', ['video', 'short']), key=prefix+'kinds')
            scopes = st.multiselect('Processamento e compartilhamento com modelos', ['local', 'external'], default=current.get('allowed_model_scopes', ['local']), key=prefix+'scopes')
            st.caption('External permite o acesso do Hermes ao material. Local restringe transcrição, candidatos e mídia à aplicação privada. Ativar exige evidência e confirmações; pendente não autoriza importação.')
            if st.form_submit_button('Salvar autorização da fonte'):
                try:
                    record = upsert_source({'channel_id': channel_id, 'name': name, 'status': status,
                        'authorization_reference': reference, 'rights_confirmed': rights,
                        'platform_permission': platform, 'allowed_languages': [v.strip() for v in languages.split(',') if v.strip()],
                        'allowed_video_kinds': kinds, 'allowed_model_scopes': scopes},
                        expected_revision=st.session_state[revision_key])
                    if current:
                        st.session_state[revision_key] = record['revision']
                    st.success(f"Fonte salva: {record['channel_id']} · {record['status']}")
                except (ValueError, PermissionError, RuntimeError) as exc:
                    st.error(str(exc))
        if records:
            st.dataframe([{'Canal': r['name'], 'ID': r['channel_id'], 'Situação': r['status'], 'Revisão': r['revision']} for r in records], hide_index=True)
