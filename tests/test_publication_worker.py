from pathlib import Path

import pytest

from app import publication_worker


def test_secret_file_and_destination_are_used_without_persisting_token(tmp_path, monkeypatch):
    secret = tmp_path / 'meta.env'
    secret.write_text('USER_ACCESS_TOKEN="private-token"\n', encoding='utf-8')
    monkeypatch.setenv('META_CREDENTIAL_FILE', str(secret))
    assert publication_worker.read_user_token() == 'private-token'
    assert 'private-token' not in repr(publication_worker.settings())


def test_missing_secret_file_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('META_CREDENTIAL_FILE', str(tmp_path / 'missing'))
    with pytest.raises(publication_worker.ConfigurationError):
        publication_worker.read_user_token()


def test_transport_checks_bound_page_and_uploads_the_selected_candidate(tmp_path, monkeypatch):
    video = tmp_path / 'master.mp4'
    video.write_bytes(b'video')
    monkeypatch.setattr(publication_worker, 'read_user_token', lambda: 'user-token')
    monkeypatch.setattr(publication_worker, 'check_video', lambda path, provider: None)
    called = []
    monkeypatch.setattr(publication_worker.meta_http, 'resolve_page', lambda api, p, i, t: called.append((p, i, t)) or 'page-token')
    monkeypatch.setattr(publication_worker.meta_transport, 'instagram', lambda api, account, token, path, caption, **kwargs: {'confirmed': True, 'remote_id': '123'})
    job = {'candidates': [{'candidate_id': 'c1', 'file': str(video)}]}
    draft = {'candidate_id': 'c1', 'provider': 'instagram', 'description': 'texto'}
    result = publication_worker.transport(draft, job, {'page_id': '100', 'instagram_id': '200'})
    assert result['confirmed'] and called == [('100', '200', 'user-token')]


def test_run_once_processes_due_items_and_continues_after_a_race(monkeypatch):
    calls = []
    monkeypatch.setattr(publication_worker.publication_schedule, 'due_items', lambda: [{'id': 'one'}, {'id': 'two'}])
    def execute(identifier, transport):
        calls.append(identifier)
        if identifier == 'one':
            raise ValueError('already cancelled')
    monkeypatch.setattr(publication_worker.publication_schedule, 'execute', execute)
    publication_worker.run_once()
    assert calls == ['one', 'two']


def test_recovery_marks_interrupted_upload_uncertain(tmp_path, monkeypatch):
    import json
    import uuid
    monkeypatch.setattr(publication_worker.publication_schedule, 'ROOT', tmp_path)
    identifier = str(uuid.uuid4())
    (tmp_path / (identifier + '.json')).write_text(json.dumps({'id': identifier, 'state': 'PUBLISHING', 'remote_container_id': '123', 'scheduled_at': 1}), encoding='utf-8')
    publication_worker.publication_schedule.recover_interrupted()
    item = publication_worker.publication_schedule.list_items()[0]
    assert item['state'] == 'UNCERTAIN' and item['remote_container_id'] == '123'


def test_heartbeat_indicates_whether_scheduler_is_running(tmp_path, monkeypatch):
    monkeypatch.setattr(publication_worker.publication_schedule, 'ROOT', tmp_path)
    assert publication_worker.publication_schedule.worker_online(now=100) is False
    publication_worker.publication_schedule.write_heartbeat(now=100)
    assert publication_worker.publication_schedule.worker_online(now=110) is True
    assert publication_worker.publication_schedule.worker_online(now=141) is False


def test_instagram_rejects_unsupported_pixel_format_before_upload(tmp_path, monkeypatch):
    import json
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'synthetic')
    probe = {'format': {'duration': '10', 'format_name': 'mov,mp4'},
             'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 720,
                          'height': 1280, 'r_frame_rate': '30/1', 'pix_fmt': 'yuv444p',
                          'bit_rate': '1000000', 'field_order': 'progressive'}]}
    monkeypatch.setattr(publication_worker.subprocess, 'check_output', lambda *args, **kwargs: json.dumps(probe).encode())
    with pytest.raises(publication_worker.ConfigurationError):
        publication_worker.check_video(video, 'instagram')


def test_invalid_nonfinite_duration_is_rejected(tmp_path, monkeypatch):
    import json
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'synthetic')
    probe = {'format': {'duration': 'NaN', 'format_name': 'mov,mp4'},
             'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 720,
                          'height': 1280, 'r_frame_rate': '30/1', 'pix_fmt': 'yuv420p'}]}
    monkeypatch.setattr(publication_worker.subprocess, 'check_output', lambda *args, **kwargs: json.dumps(probe).encode())
    with pytest.raises(publication_worker.ConfigurationError):
        publication_worker.check_video(video, 'instagram')
