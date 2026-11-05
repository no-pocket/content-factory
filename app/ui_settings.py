"""Streamlit controls for the versioned per-job processing settings."""

from .job_settings import DEFAULTS, RANGES

LABELS = {
    'clip_count': 'Quantidade de candidatos',
    'target_seconds': 'Duração alvo (segundos)',
    'min_seconds': 'Duração mínima (segundos)',
    'max_seconds': 'Duração máxima (segundos)',
    'proposal_max_chunks': 'Máximo de blocos analisados pelo Qwen',
    'shortlist': 'Candidatos enviados à classificação final',
    'ollama_timeout': 'Prazo por consulta ao Qwen (segundos)',
    'whisper_beam_size': 'Precisão de busca do Whisper (beam size)',
}


def render_settings_controls(st) -> dict:
    """Return a complete settings snapshot from a Streamlit form."""
    result = {}
    for key in DEFAULTS:
        if key in {'whisper_model', 'ranker_mode', 'llm_backend', 'director_mode', 'render_engine'}:
            labels_and_options = {
                'whisper_model': ('Modelo Whisper', ['tiny', 'base', 'small', 'medium', 'large-v3-turbo', 'large-v3']),
                'ranker_mode': ('Seleção de destaques', ['ollama', 'heuristic']),
                'llm_backend': ('Processamento do Qwen', ['ollama', 'kepler_gpu']),
                'director_mode': ('Direção de edição', ['ollama', 'heuristic']),
                'render_engine': ('Motor de render', ['remotion', 'ffmpeg']),
            }
            label, options = labels_and_options[key]
            extra = {}
            if key == 'llm_backend':
                descriptions = {'ollama': 'CPU (Ollama)', 'kepler_gpu': 'GPU K4200 (experimental)'}
                extra['format_func'] = descriptions.__getitem__
            result[key] = st.selectbox(label, options, index=options.index(DEFAULTS[key]), key=key, **extra)
        else:
            low, high = RANGES[key]
            result[key] = int(st.number_input(LABELS[key], min_value=low, max_value=high,
                                              value=DEFAULTS[key], step=1, key=key))
    return result
