"""Validated processing controls shared by all frontends and workers."""
import json

DEFAULTS = {
    'outro_asset_id': None,
    'editorial_protocol': 1,
    'retrieval_mode': 'off',
    'retrieval_dataset_id': None,
    'timeline_v3': False,
    'framing_preset': 'legacy',
    'framing_roi': None,
    'framing_windows': [],
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
    from .timeline import ASSET_ID
    ident = settings['outro_asset_id']
    if ident is not None and (not isinstance(ident, str) or not ASSET_ID.fullmatch(ident)):
        raise ValueError('Invalid outro asset ID')
    import re
    if settings['retrieval_mode'] not in ('off','lexical'):
        raise ValueError('Unsupported retrieval mode')
    dataset_id=settings['retrieval_dataset_id']
    if dataset_id is not None and (not isinstance(dataset_id,str) or not re.fullmatch('[0-9a-f]{64}',dataset_id)):
        raise ValueError('Invalid retrieval dataset ID')
    if settings['retrieval_mode']=='lexical' and (dataset_id is None or settings['editorial_protocol']!=2):
        raise ValueError('Retrieval requires dataset ID and editorial protocol 2')
    if type(settings['timeline_v3']) is not bool:
        raise ValueError('timeline_v3 must be boolean')
    if settings['timeline_v3'] and settings['editorial_protocol'] != 2:
        raise ValueError('timeline_v3 requires editorial_protocol=2')
    from .framing import PRESETS, validate_scene, normalize_source_windows
    settings['framing_windows']=normalize_source_windows(settings['framing_windows'])
    if settings['framing_windows'] and settings['framing_preset']=='legacy':
        settings['framing_preset']='web'
    if settings['framing_preset'] not in ('legacy', *PRESETS):
        raise ValueError('Unsupported framing_preset')
    roi = settings['framing_roi']
    if isinstance(roi, str):
        if len(roi) > 1000:
            raise ValueError('ROI JSON too large')
        roi = json.loads(roi) if roi.strip() else None
    if settings['framing_preset'] == 'legacy':
        if roi is not None:
            raise ValueError('Select a framing preset before supplying ROI')
    else:
        scene = validate_scene({'preset': settings['framing_preset'], 'roi': roi})
        roi = scene['roi']
    settings['framing_roi'] = roi
    for key, (low, high) in RANGES.items():
        value = settings[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer from {low} to {high}')
    if settings['whisper_model'] not in WHISPER_MODELS:
        raise ValueError('Unsupported whisper_model')
    for key, allowed in {'ranker_mode': {'heuristic', 'ollama', 'external'},
                         'llm_model': {'qwen2.5:1.5b', 'qwen2.5:3b', 'external'},
                         'llm_backend': {'ollama', 'kepler_gpu', 'external'},
                         'director_mode': {'heuristic', 'ollama', 'external'},
                         'render_engine': {'ffmpeg', 'remotion'},
                         'render_quality': {'standard', 'high'}}.items():
        if settings[key] not in allowed:
            raise ValueError(f'Unsupported {key}')
    external = [settings[key] == 'external' for key in ('ranker_mode','director_mode','llm_backend','llm_model')]
    if any(external) and not all(external):
        raise ValueError('External plans require explicit external ranker, director, backend and model')
    if not settings['min_seconds'] <= settings['target_seconds'] <= settings['max_seconds']:
        raise ValueError('min_seconds <= target_seconds <= max_seconds is required')
    if settings['shortlist'] < settings['clip_count']:
        raise ValueError('shortlist must be at least clip_count')
    return settings
