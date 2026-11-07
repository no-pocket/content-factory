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


def test_v2_retry_uses_new_paths_and_preserves_old_bytes(monkeypatch, tmp_path):
    from app import store
    calls, _ = setup(monkeypatch, tmp_path, fail=True)
    monkeypatch.setattr(store, 'OUTPUT', tmp_path)
    record = job()
    record.update(id='58924b9a-dedf-4f56-ab6d-10b25f1240b5', editorial_protocol=2)
    candidates.render_candidates(record, Path('source'), [], {}, False, only=0)
    first = Path(record['candidates'][0]['file'])
    first.write_bytes(b'keep earlier failed render for audit')
    candidates.render_candidates(record, Path('source'), [], {}, False, only=0)
    second = Path(record['candidates'][0]['file'])
    assert first != second
    assert first.read_bytes() == b'keep earlier failed render for audit'
    assert second.read_bytes() == b'master'
    assert record['candidates'][0]['render_revision'] == 2
    assert len(record['candidates'][0]['render_history']) == 1


def test_incomplete_story_fails_before_render(monkeypatch, tmp_path):
    calls, _ = setup(monkeypatch, tmp_path)
    record = job()
    record['candidates'][0]['editorial_context'] = {
        'text': 'Agora vou mostrar', 'source_range': {'start': 0, 'end': 10},
        'segments': [{'segment_id': 0, 'source_start': 0, 'source_end': 10, 'text': 'Agora vou mostrar'}],
        'before': [], 'after': []}
    candidates.render_candidates(record, Path('source'), [], {}, False, only=0)
    assert calls == []
    assert record['candidates'][0]['state'] == 'FAILED'
    assert 'incomplete' in record['candidates'][0]['attempt_history'][0]['error']


def test_millisecond_proposals_and_legacy_timeline_process(monkeypatch,tmp_path):
    from app.core import propose_clips
    from app.editorial_context import build_candidate_context
    from app.job_settings import normalize_job_settings
    segments=[{'start':.006,'end':20.004,'text':'GTA story complete.', 'words':[
        {'start':.006,'end':1,'text':'GTA'},{'start':19,'end':20.004,'text':'complete.'}]}]
    clip=propose_clips(segments,21,count=1,target=20)[0]
    assert clip['start']==.006 and clip['end']==20.004
    calls,_=setup(monkeypatch,tmp_path)
    for persisted in (False,True):
        record=job();record['candidates']=[dict(clip)]
        if persisted:
            record['candidates'][0].update(start=.01,end=20.,timeline={'duration':19.99,'schema_version':'2.0','layers':{'captions':[]}})
        record['candidates'][0]['editorial_context']=build_candidate_context(record,0,{'segments':segments})
        candidates.render_candidates(record,Path('source'),segments,normalize_job_settings(),False)
        assert record['status']=='NEEDS_REVIEW',record['candidates'][0].get('attempt_history')
        if persisted:assert record['candidates'][0]['start']==.01 and record['candidates'][0]['end']==20.
    assert len(calls)==2
