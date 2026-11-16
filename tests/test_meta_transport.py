from app import meta_transport
import pytest


@pytest.mark.parametrize('offset,expected_uploads', [(0, 2), (5, 1)])
def test_instagram_retry_only_same_session_when_remote_offset_is_zero(tmp_path, offset, expected_uploads):
    video=tmp_path/'v.mp4'; video.write_bytes(b'synthetic'); uploads=[]; created=[]
    def api(method,path,token,*,params=None,file=None,headers=None):
        if path.endswith('/media'):
            created.append(path); return {'id':'123'}
        if path=='upload/123' and method=='GET': return {'offset':offset}
        if path=='upload/123':
            uploads.append(file.read())
            if len(uploads)==1: raise ConnectionResetError('private detail')
            return {'success':True}
        if path.startswith('123?'): return {'status_code':'FINISHED' if len(uploads)>1 else 'IN_PROGRESS'}
        if path.endswith('/media_publish'): return {'id':'456'}
        if path.startswith('456?'): return {'id':'456'}
        raise AssertionError(path)
    if offset:
        with pytest.raises(ConnectionResetError): meta_transport.instagram(api,'12345','secret',video,'caption',sleep=lambda _:None)
    else:
        assert meta_transport.instagram(api,'12345','secret',video,'caption',sleep=lambda _:None)['confirmed']
    assert len(created)==1 and len(uploads)==expected_uploads
    assert all(data==b'synthetic' for data in uploads)


def test_instagram_does_not_retry_if_session_already_finished(tmp_path):
    video=tmp_path/'v.mp4'; video.write_bytes(b'synthetic'); uploads=[]
    def api(method,path,token,*,params=None,file=None,headers=None):
        if path.endswith('/media'): return {'id':'123'}
        if path=='upload/123' and method=='GET': return {'offset':0}
        if path=='upload/123': uploads.append(1); raise ConnectionResetError('connection lost')
        if path.startswith('123?'): return {'status_code':'FINISHED'}
        raise AssertionError(path)
    with pytest.raises(ConnectionResetError):
        meta_transport.instagram(api,'12345','secret',video,'caption',sleep=lambda _:None)
    assert len(uploads)==1


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
