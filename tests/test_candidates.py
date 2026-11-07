from pathlib import Path

from app import candidates


def setup(monkeypatch, tmp_path, fail=False):
    saved = []
    monkeypatch.setattr(candidates, 'save', lambda job: saved.append(job['candidates'][0].get('attempts', 0)))
    monkeypatch.setattr(candidates, 'OUTPUT', tmp_path)
    monkeypatch.setattr(candidates, 'read_assets', lambda: {})
    monkeypatch.setattr(candidates, 'direct_edit', lambda *a, **k: ({}, 'heuristic'))
    monkeypatch.setattr(candidates, 'build_timeline', lambda *a, **k: {'layers': {'captions': []}})
    calls = []
    def render(*args, **kwargs):
        calls.append(args[2])
        Path(args[7]).write_bytes(b'master')
        Path(args[7]).with_suffix('.preview.webm').write_bytes(b'preview')
        if fail:
            raise RuntimeError('interrupted renderer')
        return 'test'
    monkeypatch.setattr(candidates, 'render_edited', render)
    monkeypatch.setattr(candidates, 'inspect_candidate', lambda *a: {'state': 'VALID'})
    return calls, saved


def job():
    return {'id': 'test', 'candidates': [{'start': 0, 'end': 10}, {'start': 20, 'end': 30}]}


def test_retry_preserves_other_result_and_limits_attempts(monkeypatch, tmp_path):
    calls, saved = setup(monkeypatch, tmp_path, fail=True)
    record = job()
    record['candidates'][1].update(state='VALID', file='preserve', qc={'state': 'VALID'}, attempts=1)
    candidates.render_candidates(record, Path('source'), [], {}, False, only=0)
    assert record['status'] == 'PARTIAL_FAILED'
    assert record['candidates'][1]['file'] == 'preserve'
    assert record['candidates'][0]['attempts'] == 1
    assert len(record['candidates'][0]['attempt_history']) == 1
    assert saved[0] == 1  # attempt is persisted before rendering
    candidates.render_candidates(record, Path('source'), [], {}, False, only=0)
    assert record['candidates'][0]['attempts'] == 2
    candidates.render_candidates(record, Path('source'), [], {}, False, only=0)
    assert calls == [1, 1]


def test_resume_checks_existing_valid_result_without_rerender(monkeypatch, tmp_path):
    calls, _ = setup(monkeypatch, tmp_path)
    record = job()
    candidates.render_candidates(record, Path('source'), [], {}, False)
    assert record['status'] == 'NEEDS_REVIEW'
    assert calls == [1, 2]
    candidates.render_candidates(record, Path('source'), [], {}, False)
    assert calls == [1, 2]
    assert record['candidates'][0]['qc']['state'] == 'VALID'
