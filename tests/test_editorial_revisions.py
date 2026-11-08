import pytest

from app import store


def reviewed_job(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'JOBS', tmp_path)
    monkeypatch.setattr(store, 'OUTPUT', tmp_path / 'output')
    job = {'id': '58924b9a-dedf-4f56-ab6d-10b25f1240b5', 'status': 'APPROVED', 'editorial_protocol': 2,
           'editorial_revision': 4, 'approved': [0, 1], 'settings': {'max_seconds': 60},
           'decision_history': [{'at': 1, 'decisions': [
               {'candidate': 0, 'decision': 'APPROVED'}, {'candidate': 1, 'decision': 'APPROVED'}]}],
           'feedback_events': [{'event_id': 'keep-human-review', 'artifact_id': 'sha256:old',
                                'candidate_id': 'candidate', 'candidate_version': 1, 'render_revision': 2,
                                'created_at': '2000-01-01T00:00:00+00:00'}],
           'candidates': [{'start': 0, 'end': 20, 'candidate_id': 'candidate',
                           'candidate_version': 1, 'render_revision': 2, 'artifact_id': 'sha256:old',
                           'artifact_manifest': {'plan_sha256': 'old'}, 'state': 'VALID',
                           'attempts': 2, 'attempt_history': [{'state': 'VALID'}],
                           'file': '/old/master.mp4'},
                          {'start': 40, 'end': 60, 'state': 'VALID', 'file': '/sibling/master.mp4'}]}
    store.save(job)
    transcript = {'segments': [{'start': 0, 'end': 20, 'text': 'Conclusion.'},
                              {'start': 22, 'end': 25, 'text': 'Next.'}]}
    from app.artifacts import artifact_manifest, digest
    job['transcript_sha256'] = digest(transcript)
    folder = store.OUTPUT / job['id']
    folder.mkdir(parents=True)
    master = folder / 'old.mp4'
    master.write_bytes(b'old master keep')
    master.with_suffix('.preview.webm').write_bytes(b'old preview keep')
    job['candidates'][0]['file'] = str(master)
    job['candidates'][0]['artifact_manifest'] = artifact_manifest(job, 0)
    job['candidates'][0]['artifact_id'] = 'sha256:' + digest(job['candidates'][0]['artifact_manifest'])
    job['feedback_events'][0]['artifact_id'] = job['candidates'][0]['artifact_id']
    store.save(job)
    return job, transcript


def test_operator_revision_preserves_review_history_and_queues_fresh_pending(tmp_path, monkeypatch):
    from app.editorial_revisions import request_source_end_revision
    job, transcript = reviewed_job(tmp_path, monkeypatch)
    messages = []
    class Queue:
        def lpush(self, key, value):
            messages.append((key, value))
    result = request_source_end_revision(job['id'], 0, transcript,
        expected_artifact_id=job['candidates'][0]['artifact_id'], expected_render_revision=2,
        expected_candidate_version=1, expected_editorial_revision=4,
        reason='Complete source sentence', queue=Queue())
    assert result['status'] == 'QUEUED'
    assert result['retry_candidate'] == 0
    assert result['approved'] == [1]
    assert result['feedback_events'] == job['feedback_events']
    assert result['candidates'][1] == job['candidates'][1]
    clip = result['candidates'][0]
    assert clip['state'] == 'PENDING'
    assert clip['attempts'] == 0
    assert clip['attempt_history'] == []
    assert clip['artifact_id'] == job['candidates'][0]['artifact_id']
    assert clip['artifact_manifest'] == job['candidates'][0]['artifact_manifest']
    assert result['candidate_revision_history'][0]['candidate'] == job['candidates'][0]
    assert messages == [('clips:queue', job['id'])]
    assert store.load(job['id']) == result


@pytest.mark.parametrize('field,value', [('expected_artifact_id', 'sha256:stale'),
    ('expected_render_revision', 1), ('expected_candidate_version', 2), ('expected_editorial_revision', 3)])
def test_operator_revision_refuses_stale_parent_without_any_mutation(tmp_path, monkeypatch, field, value):
    from app.editorial_revisions import request_source_end_revision
    from app.service import Conflict
    job, transcript = reviewed_job(tmp_path, monkeypatch)
    guards = dict(expected_artifact_id=job['candidates'][0]['artifact_id'], expected_render_revision=2,
                  expected_candidate_version=1, expected_editorial_revision=4)
    guards[field] = value
    with pytest.raises(Conflict):
        request_source_end_revision(job['id'], 0, transcript, reason='Complete source sentence', **guards)
    assert store.load(job['id']) == job


def test_media_sync_revision_preserves_entire_editorial_plan(tmp_path, monkeypatch):
    from app.editorial_revisions import request_render_revision
    from app.timeline import build_timeline
    job, transcript = reviewed_job(tmp_path, monkeypatch)
    job['candidates'][0]['timeline'] = build_timeline(job['candidates'][0], transcript['segments'],
        editorial_title='Título humano')
    from app.artifacts import artifact_manifest, digest
    job['candidates'][0]['artifact_manifest'] = artifact_manifest(job, 0)
    job['candidates'][0]['artifact_id'] = 'sha256:' + digest(job['candidates'][0]['artifact_manifest'])
    store.save(job)
    class Queue:
        def lpush(self, *args):
            pass
    result = request_render_revision(job['id'], 0, transcript, kind='media_sync',
        expected_artifact_id=job['candidates'][0]['artifact_id'], expected_render_revision=2,
        expected_candidate_version=1, expected_editorial_revision=4,
        reason='Correct confirmed AV offset', queue=Queue())
    for key in ('start', 'end', 'timeline'):
        assert result['candidates'][0][key] == job['candidates'][0][key]
    assert result['candidates'][0]['state'] == 'PENDING'
    assert result['candidate_revision_history'][0]['kind'] == 'media_sync'
    assert result['feedback_events'] == job['feedback_events']


def test_operator_revision_refuses_changed_parent_bytes(tmp_path, monkeypatch):
    from pathlib import Path
    from app.editorial_revisions import request_source_end_revision
    from app.service import Conflict
    job, transcript = reviewed_job(tmp_path, monkeypatch)
    Path(job['candidates'][0]['file']).write_bytes(b'changed since review')
    with pytest.raises(Conflict, match='bytes or plan changed'):
        request_source_end_revision(job['id'], 0, transcript,
            expected_artifact_id=job['candidates'][0]['artifact_id'], expected_render_revision=2,
            expected_candidate_version=1, expected_editorial_revision=4, reason='Complete sentence')
    assert store.load(job['id']) == job


def test_operator_revision_render_gets_new_version_and_keeps_old_artifacts_and_review(tmp_path, monkeypatch):
    from pathlib import Path
    from app import candidates
    from app.editorial_revisions import request_source_end_revision
    job, transcript = reviewed_job(tmp_path, monkeypatch)
    class Queue:
        def lpush(self, *args):
            pass
    revised = request_source_end_revision(job['id'], 0, transcript,
        expected_artifact_id=job['candidates'][0]['artifact_id'], expected_render_revision=2,
        expected_candidate_version=1, expected_editorial_revision=4,
        reason='Complete sentence', queue=Queue())
    monkeypatch.setattr(candidates, 'OUTPUT', store.OUTPUT)
    monkeypatch.setattr(candidates, 'read_assets', lambda: {})
    monkeypatch.setattr(candidates, 'inspect_candidate', lambda *a: {'state': 'VALID'})
    def render(*args, **kwargs):
        target = Path(args[7])
        target.write_bytes(b'new master')
        target.with_suffix('.preview.webm').write_bytes(b'new preview')
        return 'test_renderer'
    monkeypatch.setattr(candidates, 'render_edited', render)
    candidates.render_candidates(revised, Path('/source'), transcript['segments'], {}, True, only=0)
    clip = revised['candidates'][0]
    assert clip['state'] == 'VALID', clip['attempt_history']
    assert clip['candidate_version'] == 2
    assert clip['render_revision'] == 3
    assert clip['render_history'][0]['artifact_id'] == job['candidates'][0]['artifact_id']
    assert Path(job['candidates'][0]['file']).read_bytes() == b'old master keep'
    assert Path(job['candidates'][0]['file']).with_suffix('.preview.webm').read_bytes() == b'old preview keep'
    assert clip['file'] != job['candidates'][0]['file']
    assert revised['feedback_events'] == job['feedback_events']
    assert revised['candidate_revision_history'][0]['candidate']['attempt_history'] == [{'state': 'VALID'}]
    assert revised['approved'] == [1]
    from app.service import get_editorial_view
    from app.review_queue import needs_review
    view = get_editorial_view(revised)
    assert view['candidates'][0]['normalized_decision'] == 'PENDING'
    assert view['candidates'][0]['legacy_decision'] is None
    assert view['candidates'][1]['legacy_decision'] == 'APPROVED'
    assert needs_review(revised)
