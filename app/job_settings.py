"""Validated processing controls shared by all frontends and workers."""

DEFAULTS = {
    'editorial_protocol': 1,
    'clip_count': 3,
    'target_seconds': 40,
    'min_seconds': 15,
    'max_seconds': 60,
    'proposal_max_chunks': 12,
    'shortlist': 12,
    'ollama_timeout': 180,
    'whisper_model': 'base',
    'whisper_beam_size': 5,
    'ranker_mode': 'ollama',
    'llm_backend': 'ollama',
    'llm_model': 'qwen2.5:3b',
    'director_mode': 'ollama',
    'render_engine': 'remotion',
    'render_quality': 'high',
}

RANGES = {
    'editorial_protocol': (1, 2),
    'clip_count': (1, 6),
    'target_seconds': (8, 60),
    'min_seconds': (8, 60),
    'max_seconds': (15, 60),
    'proposal_max_chunks': (1, 32),
    'shortlist': (3, 32),
    'ollama_timeout': (15, 600),
    'whisper_beam_size': (1, 10),
}
WHISPER_MODELS = {'tiny', 'base', 'small', 'medium', 'large-v3', 'large-v3-turbo'}


def normalize_job_settings(overrides: dict | None = None) -> dict:
    """Return a complete, bounded settings snapshot for one job."""
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError('settings must be an object')
    unknown = set(overrides) - set(DEFAULTS)
    if unknown:
        raise ValueError(f'Unknown settings: {", ".join(sorted(unknown))}')
    settings = {**DEFAULTS, **overrides}
    for key, (low, high) in RANGES.items():
        value = settings[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer from {low} to {high}')
    if settings['whisper_model'] not in WHISPER_MODELS:
        raise ValueError('Unsupported whisper_model')
    for key, allowed in {'ranker_mode': {'heuristic', 'ollama'},
                         'llm_model': {'qwen2.5:1.5b', 'qwen2.5:3b'},
                         'llm_backend': {'ollama', 'kepler_gpu'},
                         'director_mode': {'heuristic', 'ollama'},
                         'render_engine': {'ffmpeg', 'remotion'},
                         'render_quality': {'standard', 'high'}}.items():
        if settings[key] not in allowed:
            raise ValueError(f'Unsupported {key}')
    if not settings['min_seconds'] <= settings['target_seconds'] <= settings['max_seconds']:
        raise ValueError('min_seconds <= target_seconds <= max_seconds is required')
    if settings['shortlist'] < settings['clip_count']:
        raise ValueError('shortlist must be at least clip_count')
    return settings
