"""Streamlit doctor component; intentionally does not start inference."""
from __future__ import annotations
import time
import streamlit as st
from .doctor import snapshot
from .store import all_jobs, rconn

ACTIVE = {'queued', 'analyzing'}


def render_doctor() -> None:
    st.subheader('🩺 Doctor — AI Health Check')
    info = snapshot(rconn())
    worker = info['worker']
    ollama = info['ollama']
    ranker = info['ranker']
    a, b, c, d = st.columns(4)
    a.metric('Worker', 'Online' if worker.get('online') else 'Offline')
    b.metric('Ranker ativo no worker', ranker)
    c.metric('Ollama API', 'Online' if ollama['reachable'] else 'Offline')
    d.metric('Modelo instalado', 'Sim' if ollama['installed'] else 'Não')
    st.caption(f"Modelo esperado: `{ollama['model']}` · Carregado no Ollama agora: {'Sim' if ollama['loaded'] else 'Não'} · GPU/CPU: verificar `ollama ps` no host")
    st.caption(f"Editor: `{worker.get('edit_director', 'desconhecido')}` · Renderer: `{worker.get('render_engine', 'desconhecido')}`")
    if not worker.get('online'):
        st.error('Worker sem heartbeat recente. O estado de CLIP_RANKER não pode ser confirmado.')
    elif ranker != 'ollama':
        st.warning('Worker está configurado para heurística. Ollama online, sozinho, não significa que a IA esteja selecionando cortes.')
    elif not ollama['reachable'] or not ollama['installed']:
        st.error('IA configurada, mas Ollama ou o modelo não está disponível. Novos jobs podem usar fallback heurístico.')
    else:
        st.success('Worker configurado para Ollama; serviço e modelo disponíveis. O uso real é registrado por job abaixo.')
    if ollama.get('error'):
        st.caption('Ollama: ' + ollama['error'])
    if worker.get('error'):
        st.caption('Worker: ' + worker['error'])

    current = [j for j in all_jobs() if j.get('ai_activity', {}).get('state') in ACTIVE and j.get('status') in ('TRANSCRIBING', 'RENDERING')]
    if current and not worker.get('online'):
        st.warning('Existem análises sem conclusão registrada, mas o worker está offline. A inferência não pode ser confirmada.')
    elif current:
        for j in sorted(current, key=lambda item: item.get('ai_activity', {}).get('updated_at', 0), reverse=True)[:3]:
            activity = j['ai_activity']
            elapsed = int(max(0, time.time() - activity.get('started_at', activity.get('updated_at', time.time()))))
            if activity.get('state') == 'analyzing' and time.time() - activity.get('updated_at', 0) > 600:
                st.warning(f"Job `{j['id'][:8]}` com análise antiga sem conclusão registrada; confira logs do worker.")
            elif activity.get('state') == 'analyzing':
                st.markdown('<span class="ai-dot"></span> **Qwen trabalhando — inferência em andamento**', unsafe_allow_html=True)
                st.caption(f"Job `{j['id'][:8]}` · {activity.get('total_candidates', '?')} candidatos enviados em um lote · {elapsed}s decorridos")
                st.caption('⏳ Resposta em andamento; o Ollama não informa progresso por candidato nesta chamada.')
            else:
                st.info(f"Job `{j['id'][:8]}` · Preparando análise por IA")
    else:
        st.info('Sem análise por IA em andamento neste momento.')
    editing = [j for j in all_jobs() if j.get('editing_activity', {}).get('state') == 'analyzing' and j.get('status') == 'DIRECTING']
    if editing and worker.get('online'):
        st.markdown('<span class="ai-dot"></span> **Qwen Editing Director está criando a timeline**', unsafe_allow_html=True)
        st.caption(f"Job `{editing[-1]['id'][:8]}` · Inferência de edição em andamento.")
    st.caption('A atividade vem de eventos emitidos pelo worker. O progresso é indeterminado porque o modelo analisa os candidatos em uma única requisição.')


def render_job_ai(job: dict) -> None:
    used = job.get('ranker_used')
    state = job.get('ai_activity', {}).get('state', 'unknown')
    if used == 'ollama':
        st.success('Este job foi classificado pelo Qwen local (resposta válida).')
    elif used == 'heuristic_fallback':
        st.warning('Este job usou fallback heurístico: ' + job.get('ai_activity', {}).get('reason', 'sem motivo registrado'))
    elif used == 'heuristic':
        st.info('Este job foi classificado pela heurística (IA desativada).')
    elif state == 'analyzing':
        st.info('Qwen está avaliando os candidatos. Aguardando resultado.')
    elif state == 'queued':
        st.info('Análise por IA agendada.')
    elif used == 'ollama_pending':
        st.warning('Análise interrompida antes de um resultado confirmado.')
    else:
        st.caption('Motor efetivo não registrado (job anterior à v3.2 ou ainda transcrevendo).')
    activity = job.get('ai_activity', {})
    if activity.get('elapsed_seconds') is not None:
        st.caption(f"Tempo de análise: {activity['elapsed_seconds']}s")
