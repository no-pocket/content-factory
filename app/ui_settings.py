"""Streamlit controls for the versioned per-job processing settings."""

from .job_settings import DEFAULTS, RANGES

LABELS = {
    'editorial_protocol': 'Protocolo editorial (1 legado, 2 revisão versionada)',
    'clip_count': 'Quantidade de candidatos',
    'target_seconds': 'Duração alvo (segundos)',
    'min_seconds': 'Duração mínima (segundos)',
    'max_seconds': 'Duração máxima (segundos)',
    'proposal_max_chunks': 'Máximo de blocos analisados pelo Qwen',
    'shortlist': 'Candidatos enviados à classificação final',
    'ollama_timeout': 'Prazo por consulta ao Qwen (segundos)',
    'whisper_beam_size': 'Precisão de busca do Whisper (beam size)',
}


def render_settings_controls(st, *, preferred: dict | None = None, key_prefix: str = '') -> dict:
    """Return a complete settings snapshot from a Streamlit form."""
    initial = {**DEFAULTS, **(preferred or {})}
    result = {}
    for key in DEFAULTS:
        if key in {'whisper_model', 'ranker_mode', 'llm_backend', 'llm_model', 'director_mode', 'render_engine', 'render_quality'}:
            labels_and_options = {
                'whisper_model': ('Modelo Whisper', ['tiny', 'base', 'small', 'medium', 'large-v3-turbo', 'large-v3']),
                'ranker_mode': ('Seleção de destaques', ['ollama', 'heuristic']),
                'llm_backend': ('Processamento do Qwen', ['ollama', 'kepler_gpu']),
                'llm_model': ('Modelo Qwen por job', ['qwen2.5:3b', 'qwen2.5:1.5b']),
                'director_mode': ('Direção de edição', ['ollama', 'heuristic']),
                'render_engine': ('Motor de render', ['remotion', 'ffmpeg']),
                'render_quality': ('Qualidade de imagem', ['high', 'standard']),
            }
            label, options = labels_and_options[key]
            extra = {}
            if key == 'llm_backend':
                descriptions = {'ollama': 'CPU (Ollama)', 'kepler_gpu': 'GPU K4200 (experimental)'}
                extra['format_func'] = descriptions.__getitem__
            if key == 'render_quality':
                extra['format_func'] = {'high':'Alta fidelidade (perfil aprovado)', 'standard':'Legado/econômico'}.__getitem__
            result[key] = st.selectbox(label, options, index=options.index(initial[key]), key=key_prefix+key, **extra)
        else:
            low, high = RANGES[key]
            result[key] = int(st.number_input(LABELS[key], min_value=low, max_value=high,
                                              value=initial[key], step=1, key=key_prefix+key))
    return result
