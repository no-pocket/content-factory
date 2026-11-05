from types import SimpleNamespace

from app import worker
from app.job_settings import normalize_job_settings


def test_ranker_records_gpu_backend_after_valid_reply(monkeypatch):
    monkeypatch.setattr(worker, 'save', lambda job: None)
    job = {'id': 'gpu-fixture', 'settings': {'llm_backend': 'kepler_gpu'}}
    worker.record_ai_event(job, 'analyzing', {})
    worker.record_ai_event(job, 'completed', {})
    assert job['ranker_used'] == 'kepler_gpu'


def test_worker_uses_job_settings_for_transcription_and_highlights(monkeypatch, tmp_path):
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'fixture')
    settings = normalize_job_settings({'clip_count': 1, 'target_seconds': 25,
                                       'whisper_model': 'small', 'whisper_beam_size': 3,
                                       'director_mode': 'heuristic', 'render_engine': 'ffmpeg',
                                       'llm_backend': 'kepler_gpu'})
    job = {'id': 'fixture', 'status': 'QUEUED', 'source': str(source), 'settings': settings}
    observed = {}
    monkeypatch.setattr(worker, 'load', lambda jid: job)
    monkeypatch.setattr(worker, 'save', lambda value: None)
    monkeypatch.setattr(worker, 'get_duration', lambda path: 100.0)
    monkeypatch.setattr(worker, 'JOBS', tmp_path)
    monkeypatch.setattr(worker, 'OUTPUT', tmp_path)
    monkeypatch.setenv('CLIP_RANKER', 'ollama')

    class Model:
        def __init__(self, name, **kwargs):
            observed['model'] = name
        def transcribe(self, path, **kwargs):
            observed['beam'] = kwargs['beam_size']
            segment = SimpleNamespace(start=10, end=40, text='Uma ideia completa', words=[])
            return [segment], SimpleNamespace(language='pt')
    monkeypatch.setattr(worker, 'WhisperModel', Model)
    def select(segments, duration, **kwargs):
        observed['count'] = kwargs['count']
        observed['settings'] = kwargs['settings']
        return [{'start': 10, 'end': 40, 'text': 'Uma ideia completa', 'score': 1}]
    monkeypatch.setattr(worker, 'select_highlights', select)
    monkeypatch.setattr(worker, 'read_assets', lambda: {})
    def direct(*args, **kwargs):
        observed['director_mode'] = kwargs['mode']
        observed['llm_backend'] = kwargs['llm_backend']
        return {}, 'heuristic'
    monkeypatch.setattr(worker, 'direct_edit', direct)
    monkeypatch.setattr(worker, 'build_timeline', lambda *a, **k: {'layers': {'captions': []}})
    def render(*args, **kwargs):
        observed['render_engine'] = kwargs['engine']
        return 'fake'
    monkeypatch.setattr(worker, 'render_edited', render)

    worker.process('fixture')
    assert job['status'] == 'NEEDS_REVIEW'
    assert (observed['model'], observed['beam'], observed['count']) == ('small', 3, 1)
    assert observed['settings']['target_seconds'] == 25
    assert observed['llm_backend'] == 'kepler_gpu'
    assert (observed['director_mode'], observed['render_engine']) == ('heuristic', 'ffmpeg')
