"""Calendar presentation and explicit timezone conversion."""
from __future__ import annotations

import calendar
import time
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def month_grid(year: int, month: int) -> list[list[int]]:
    return calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)


def caption_key(job_id: str, candidate_id: str, artifact_id: str, provider: str) -> str:
    return f'social_caption:{job_id}:{candidate_id}:{artifact_id}:{provider}'


def local_timestamp(day, clock, timezone_name: str) -> float:
    zone = ZoneInfo(timezone_name)
    naive = datetime.combine(day, clock)
    local = naive.replace(tzinfo=zone)
    if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive:
        raise ValueError('Horário local inexistente')
    if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError('Horário local ambíguo')
    return local.timestamp()


def render(st, jobs: list[dict]) -> None:
    from . import publication_schedule as agenda
    from . import service

    st.subheader('Agenda de publicações')
    st.caption('A publicação depende do serviço de agenda e da workstation ligada. O horário é local de São Paulo.')
    if agenda.worker_online():
        st.caption('Serviço da agenda ativo.')
    else:
        st.warning('Serviço da agenda indisponível; publicações aguardam até ele voltar.')
    if st.button('Atualizar agenda', key='refresh_publication_calendar'):
        st.rerun()
    zone = ZoneInfo('America/Sao_Paulo')
    today = datetime.now(zone).date()
    columns = st.columns(2)
    year = int(columns[0].number_input('Ano', min_value=2024, max_value=2100, value=today.year, key='agenda_year'))
    month = int(columns[1].number_input('Mês', min_value=1, max_value=12, value=today.month, key='agenda_month'))
    items = agenda.list_items()
    header = st.columns(7)
    for col, label in zip(header, ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']):
        col.markdown('**' + label + '**')
    icons = {'SCHEDULED': '🕒', 'SENDING': '⬆️', 'PROCESSING': '⏳', 'PUBLISHING': '⏳', 'PUBLISHED': '✅', 'BLOCKED': '⛔', 'CANCELLED': '🚫', 'UNCERTAIN': '⚠️'}
    for week in month_grid(year, month):
        cells = st.columns(7)
        for col, day in zip(cells, week):
            if day:
                col.markdown('**' + str(day) + '**')
                for item in items:
                    instant = datetime.fromtimestamp(item['scheduled_at'], zone)
                    if instant.date() == date(year, month, day):
                        col.caption(f"{icons.get(item['state'], '•')} {instant:%H:%M} {item['draft']['provider']}")

    choices = []
    for job in jobs:
        if job.get('editorial_protocol') != 2:
            continue
        for row in service.get_editorial_view(job)['candidates']:
            if row.get('normalized_decision') == 'APPROVED' and row.get('artifact_intact'):
                choices.append((job, job['candidates'][row['original_index']]))
    if choices:
        selected = st.selectbox('Candidato aprovado', range(len(choices)),
                                format_func=lambda i: f"{choices[i][0]['id'][:8]} · {choices[i][1]['candidate_id']}")
        job, clip = choices[selected]
        suggestions = clip.get('social_captions', {})
        if not suggestions:
            st.info('Este candidato ainda não tem sugestões de legenda.')
        if st.button('Gerar novas sugestões de legenda', key='generate_social_captions'):
            from .social_captions import regenerate
            try:
                with st.spinner('Criando sugestões a partir da transcrição...'):
                    regenerate(job['id'], clip['candidate_id'], clip['artifact_id'])
                st.success('Sugestões atualizadas. Edições já digitadas foram preservadas.')
                st.rerun()
            except (ValueError, service.Conflict, OSError) as exc:
                st.error(f'Não foi possível gerar as sugestões: {exc}')
        destinations = st.multiselect('Destinos', ['instagram', 'facebook'])
        drafts = st.session_state.setdefault('social_caption_drafts', {})
        captions = {}
        for provider in destinations:
            key = caption_key(job['id'], clip['candidate_id'], clip['artifact_id'], provider)
            suggestion = suggestions.get(provider, {})
            if key not in st.session_state:
                st.session_state[key] = drafts.get(key, suggestion.get('text', ''))
            if suggestion.get('text') and st.button('Usar sugestão para ' + provider.title(), key='apply_' + key):
                st.session_state[key] = suggestion['text']
                drafts[key] = suggestion['text']
            def save_caption(widget_key=key):
                st.session_state['social_caption_drafts'][widget_key] = st.session_state[widget_key]
            captions[provider] = st.text_area('Legenda para ' + provider.title(), key=key, on_change=save_caption)
            if suggestion:
                from .social_captions import ORIGIN_LABELS, REASON_LABELS
                origin = suggestion.get('origin', 'desconhecida')
                reason = suggestion.get('reason')
                st.caption('Sugestão: ' + ORIGIN_LABELS.get(origin, 'desconhecida') +
                           (' · ' + REASON_LABELS.get(reason, 'motivo não informado') if reason else ''))
        with st.form('agenda_form'):
            page_id = st.text_input('ID da Página do Facebook')
            instagram_id = st.text_input('ID da conta profissional do Instagram')
            title = st.text_input('Título')
            st.caption('O título identifica o item na agenda e acompanha o Reel no Facebook; o Instagram usa a legenda.')
            timing = st.radio('Quando publicar', ['Agora', 'Agendar'], horizontal=True)
            target_date = st.date_input('Data', value=today)
            target_time = st.time_input('Hora', value=datetime.now(zone).time().replace(second=0, microsecond=0))
            submit = st.form_submit_button('Confirmar publicação')
        if submit:
            try:
                if not destinations:
                    raise ValueError('Escolha pelo menos um destino')
                when = time.time() if timing == 'Agora' else local_timestamp(target_date, target_time, zone.key)
                if timing == 'Agendar' and when <= time.time():
                    raise ValueError('Escolha um horário futuro')
                if not page_id.isdecimal() or ('instagram' in destinations and not instagram_id.isdecimal()):
                    raise ValueError('Informe IDs numéricos das contas')
                created, failures = [], []
                for provider in destinations:
                    try:
                        agenda.schedule(job['id'], clip['candidate_id'], provider, title=title,
                                        caption=captions[provider], scheduled_at=when, page_id=page_id,
                                        instagram_id=instagram_id if provider == 'instagram' else None,
                                        timezone_name=zone.key)
                        created.append(provider)
                    except (ValueError, service.Conflict, OSError):
                        failures.append(provider)
                if created:
                    st.success('Adicionado à agenda: ' + ', '.join(created))
                if failures:
                    st.error('Não foi possível agendar: ' + ', '.join(failures) + '. Confira aprovação, QC e dados do destino.')
                    if created:
                        st.warning('Os destinos já adicionados continuam agendados. Confira a agenda antes de tentar novamente.')
                if not failures:
                    st.rerun()
            except (ValueError, service.Conflict, OSError) as exc:
                st.error(f'Não foi possível agendar: {exc}')
    else:
        st.info('Aprove um candidato na revisão editorial para agendar.')

    for item in reversed(items):
        instant = datetime.fromtimestamp(item['scheduled_at'], zone)
        with st.expander(f"{icons.get(item['state'], '•')} {instant:%d/%m/%Y %H:%M} · {item['draft']['provider']} · {item['state']}"):
            st.write(f"Candidato: {item['draft']['candidate_id']} · {item['draft']['title']}")
            if item.get('remote_container_id'):
                st.caption('ID da sessão na Meta: ' + str(item['remote_container_id']))
            if item.get('remote_id'):
                st.caption('ID da publicação: ' + str(item['remote_id']))
            if item.get('permalink'):
                link = item['permalink']
                if link.startswith('/'):
                    link = 'https://www.facebook.com' + link
                if link.startswith(('https://www.facebook.com/', 'https://www.instagram.com/')):
                    st.link_button('Ver publicação', link)
            if item.get('error'):
                st.warning(item['error'])
            if item['state'] == 'SCHEDULED':
                with st.form('reschedule_' + item['id']):
                    new_date = st.date_input('Nova data', value=instant.date())
                    new_time = st.time_input('Nova hora', value=instant.time().replace(second=0, microsecond=0))
                    change = st.form_submit_button('Alterar agendamento')
                if change:
                    try:
                        new_instant = local_timestamp(new_date, new_time, zone.key)
                        if new_instant <= time.time():
                            raise ValueError('Escolha um horário futuro')
                        agenda.reschedule(item['id'], new_instant, zone.key)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                if st.button('Cancelar agendamento', key='cancel_' + item['id']):
                    try:
                        agenda.cancel(item['id'])
                        st.rerun()
                    except ValueError:
                        st.warning('O envio já começou; o agendamento não pode ser cancelado.')
