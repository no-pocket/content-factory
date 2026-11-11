"""Meta protocol helpers; an injected client owns credentials and HTTP."""
from __future__ import annotations

import time
from pathlib import Path


def instagram(api, account_id: str, token: str, video: Path, caption: str, *, sleep=time.sleep, progress=lambda *_: None) -> dict:
    if not account_id.isdecimal():
        raise ValueError('invalid Instagram account')
    result = api('POST', account_id + '/media', token,
                 params={'media_type': 'REELS', 'upload_type': 'resumable', 'caption': caption})
    container = str(result.get('id', ''))
    if not container.isdecimal():
        raise RuntimeError('Instagram did not return a container')
    progress('SENDING', container)
    with video.open('rb') as stream:
        result = api('POST', 'upload/' + container, token, file=stream,
                     headers={'offset': '0', 'file_size': str(video.stat().st_size)})
    if result.get('success') is not True:
        raise RuntimeError('Instagram upload failed')
    progress('PROCESSING', container)
    for _ in range(5):
        result = api('GET', container + '?fields=status_code,status', token)
        status = result.get('status_code')
        if status == 'FINISHED':
            break
        if status != 'IN_PROGRESS':
            raise RuntimeError('Instagram container failed')
        sleep(60)
    else:
        raise TimeoutError('Instagram processing timed out')
    progress('PUBLISHING', container)
    result = api('POST', account_id + '/media_publish', token, params={'creation_id': container})
    media = str(result.get('id', ''))
    if not media.isdecimal():
        raise RuntimeError('Instagram publication is not confirmed')
    details = api('GET', media + '?fields=id,permalink,media_type', token)
    if str(details.get('id', '')) != media:
        raise RuntimeError('Instagram media verification failed')
    return {'confirmed': True, 'remote_id': media, 'permalink': details.get('permalink')}


def facebook(api, token: str, video: Path, caption: str, *, title: str = '', sleep=time.sleep, progress=lambda *_: None) -> dict:
    result = api('POST', 'me/video_reels', token, params={'upload_phase': 'start'})
    media = str(result.get('video_id', ''))
    if not media.isdecimal():
        raise RuntimeError('Facebook did not return a video ID')
    progress('SENDING', media)
    with video.open('rb') as stream:
        result = api('POST', 'facebook_upload/' + media, token, file=stream,
                     headers={'offset': '0', 'file_size': str(video.stat().st_size)})
    if result.get('success') is not True:
        raise RuntimeError('Facebook upload failed')
    progress('PUBLISHING', media)
    result = api('POST', 'me/video_reels', token,
                 params={'upload_phase': 'finish', 'video_id': media,
                         'video_state': 'PUBLISHED', 'description': caption, 'title': title})
    if result.get('success') is not True:
        raise RuntimeError('Facebook did not accept finalization')
    progress('PROCESSING', media)
    for _ in range(5):
        result = api('GET', media + '?fields=status,permalink_url', token)
        phase = result.get('status', {}).get('publishing_phase', {})
        if phase.get('status') == 'complete' and phase.get('publish_status') == 'published':
            return {'confirmed': True, 'remote_id': media, 'permalink': result.get('permalink_url')}
        if result.get('status', {}).get('video_status') == 'error':
            raise RuntimeError('Facebook processing failed')
        sleep(60)
    raise TimeoutError('Facebook publication not confirmed')
