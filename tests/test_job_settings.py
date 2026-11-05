import pytest

from app.job_settings import normalize_job_settings


def test_llm_backend_is_selectable_per_job():
    assert normalize_job_settings({'llm_backend': 'kepler_gpu'})['llm_backend'] == 'kepler_gpu'


def test_job_settings_accept_valid_per_job_overrides():
    settings = normalize_job_settings({
        'clip_count': 5, 'target_seconds': 30, 'min_seconds': 12,
        'max_seconds': 50, 'proposal_max_chunks': 6, 'shortlist': 18,
        'ollama_timeout': 90, 'whisper_model': 'small', 'whisper_beam_size': 3,
        'ranker_mode': 'heuristic', 'director_mode': 'heuristic', 'render_engine': 'ffmpeg',
    })
    assert settings['clip_count'] == 5
    assert settings['proposal_max_chunks'] == 6
    assert settings['whisper_model'] == 'small'
    assert settings['render_engine'] == 'ffmpeg'


@pytest.mark.parametrize('override', [
    {'clip_count': 0}, {'clip_count': True}, {'max_seconds': 90},
    {'min_seconds': 50, 'target_seconds': 40},
    {'shortlist': 2}, {'proposal_max_chunks': 0},
    {'ollama_timeout': 5}, {'whisper_model': 'unsupported'},
    {'whisper_beam_size': 0}, {'ranker_mode': 'cloud'},
    {'director_mode': 'cloud'}, {'render_engine': 'moviepy'}, {'unknown': 1},
])
def test_job_settings_reject_invalid_values(override):
    with pytest.raises(ValueError):
        normalize_job_settings(override)
