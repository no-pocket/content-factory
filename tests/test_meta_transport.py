from app import meta_transport


def test_instagram_direct_upload_confirms_publication(tmp_path):
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'synthetic')
    calls = []
    def api(method, path, token, *, params=None, file=None, headers=None):
        calls.append((method, path, params))
        if path.endswith('/media'):
            return {'id': '123'}
        if path.startswith('upload/'):
            assert file.read() == b'synthetic'
            return {'success': True}
        if path.startswith('123?'):
            return {'status_code': 'FINISHED'}
        if path.endswith('/media_publish'):
            return {'id': '456'}
        if path.startswith('456?'):
            return {'id': '456', 'permalink': 'https://www.instagram.com/reel/example/'}
        raise AssertionError(path)
    result = meta_transport.instagram(api, '12345', 'secret', video, 'teste', sleep=lambda _: None)
    assert result['confirmed'] and result['remote_id'] == '456'
    assert calls[0][2]['upload_type'] == 'resumable'


def test_facebook_waits_for_published_status(tmp_path):
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'synthetic')
    def api(method, path, token, *, params=None, file=None, headers=None):
        if path == 'me/video_reels' and params['upload_phase'] == 'start':
            return {'video_id': '123'}
        if path == 'facebook_upload/123':
            assert file.read() == b'synthetic'
            return {'success': True}
        if path == 'me/video_reels' and params['upload_phase'] == 'finish':
            assert params['title'] == 'Título escolhido'
            return {'success': True}
        if path.startswith('123?'):
            return {'status': {'publishing_phase': {'status': 'complete', 'publish_status': 'published'}}, 'permalink_url': '/reel/123/'}
        raise AssertionError(path)
    assert meta_transport.facebook(api, 'secret', video, 'teste', title='Título escolhido', sleep=lambda _: None)['confirmed']
