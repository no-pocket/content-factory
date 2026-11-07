from types import SimpleNamespace

from app import worker
from app.job_settings import normalize_job_settings


def test_ranker_records_gpu_backend_after_valid_reply(monkeypatch):
    monkeypatch.setattr(worker, 'save', lambda job: None)
    job = {'id': 'gpu-fixture', 'settings': {'llm_backend': 'kepler_gpu'}}
    worker.record_ai_event(job, 'analyzing', {})
    worker.record_ai_event(job, 'completed', {})
    assert job['ranker_used'] == 'kepler_gpu'


def test_completed_analysis_keeps_earlier_fallback_diagnostics(monkeypatch):
    monkeypatch.setattr(worker, 'save', lambda job: None)
    job = {'id': 'synthetic-events', 'settings': {'llm_backend': 'ollama'}}
    worker.record_ai_event(job, 'proposal_chunk_rejected', {'reason': 'No valid duration'})
    worker.record_ai_event(job, 'completed', {'selected_count': 3})
    assert [e['event'] for e in job['ai_events']] == ['proposal_chunk_rejected', 'completed']
    assert job['ai_events'][0]['details']['reason'] == 'No valid duration'


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
    monkeypatch.setenv('CLIP_RANKER', 'ollama')

    class Model:
        def __init__(self, name, **kwargs):
            observed['model'] = name
        def transcribe(self, path, **kwargs):
            observed['beam'] = kwargs['beam_size']
            assert 'language' not in kwargs  # multilingual corpus: automatic language detection
            assert kwargs.get('task', 'transcribe') == 'transcribe'  # preserve original speech
            segment = SimpleNamespace(start=10, end=40, text='Uma ideia completa', words=[])
            return [segment], SimpleNamespace(language='pt')
    monkeypatch.setattr(worker, 'WhisperModel', Model)
    def select(segments, duration, **kwargs):
        observed['count'] = kwargs['count']
        observed['settings'] = kwargs['settings']
        return [{'start': 10, 'end': 40, 'text': 'Uma ideia completa', 'score': 1}]
    monkeypatch.setattr(worker, 'select_highlights', select)
    monkeypatch.setattr(worker, 'expects_audio', lambda path: True)
    def render(record, source, segments, settings, audio_expected, **kwargs):
        observed['director_mode'] = settings['director_mode']
        observed['llm_backend'] = settings['llm_backend']
        observed['render_engine'] = settings['render_engine']
        record['status'] = 'NEEDS_REVIEW'
    monkeypatch.setattr(worker, 'render_candidates', render)

    worker.process('fixture')
    assert job['status'] == 'NEEDS_REVIEW'
    assert (observed['model'], observed['beam'], observed['count']) == ('small', 3, 1)
    assert observed['settings']['target_seconds'] == 25
    assert observed['llm_backend'] == 'kepler_gpu'
    assert (observed['director_mode'], observed['render_engine']) == ('heuristic', 'ffmpeg')
