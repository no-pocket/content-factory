"""Small HTTPS-only Meta Graph client, with no redirects or token-bearing URLs."""
from __future__ import annotations

import http.client
import json
import re
import urllib.parse


class MetaHTTPError(RuntimeError):
    pass


def resolve_page(api, page_id: str, instagram_id: str | None, user_token: str) -> str:
    if not page_id.isdecimal() or (instagram_id is not None and not instagram_id.isdecimal()):
        raise ValueError('invalid account ID')
    response = api('GET', page_id + '?fields=name,access_token,instagram_business_account', user_token)
    if str(response.get('id', '')) != page_id or not response.get('access_token'):
        raise ValueError('Page access unavailable')
    if instagram_id is not None and str(response.get('instagram_business_account', {}).get('id', '')) != instagram_id:
        raise ValueError('Instagram account changed')
    return response['access_token']


class MetaHTTP:
    def __init__(self, version: str, *, timeout: int = 90):
        if not re.fullmatch(r'v[0-9]{1,2}\.0', version):
            raise ValueError('invalid Meta API version')
        self.version = version
        self.timeout = timeout

    def __call__(self, method, path, token, *, params=None, file=None, headers=None):
        if not isinstance(token, str) or not token or '\n' in token or '\r' in token:
            raise ValueError('invalid Meta token')
        match = re.fullmatch(r'(upload|facebook_upload)/([0-9]+)', path)
        if match:
            if method != 'POST' or file is None or params is not None:
                raise ValueError('invalid upload')
            prefix = 'ig-api-upload' if match[1] == 'upload' else 'video-upload'
            host = 'rupload.facebook.com'
            request_path = f'/{prefix}/{self.version}/{match[2]}'
        else:
            if not re.fullmatch(r'(?:[0-9]+/(?:media|media_publish)|me/video_reels|[0-9]+\?fields=status_code,status|[0-9]+\?fields=id,permalink,media_type|[0-9]+\?fields=status,permalink_url|[0-9]+\?fields=name,access_token,instagram_business_account)', path):
                raise ValueError('invalid Graph API path')
            if method not in ('GET', 'POST') or file is not None:
                raise ValueError('invalid Graph request')
            host, request_path = 'graph.facebook.com', f'/{self.version}/{path}'
        if headers and (set(headers) != {'offset', 'file_size'} or any(not str(x).isdigit() for x in headers.values())):
            raise ValueError('invalid upload headers')
        payload = urllib.parse.urlencode(params or {}).encode('utf-8') if method == 'POST' and file is None else b''
        conn = http.client.HTTPSConnection(host, timeout=self.timeout)
        try:
            conn.putrequest(method, request_path)
            conn.putheader('Authorization', ('OAuth ' if match else 'Bearer ') + token)
            if file is not None:
                if headers is None:
                    raise ValueError('missing upload length')
                conn.putheader('Content-Type', 'application/octet-stream')
                conn.putheader('Content-Length', str(headers['file_size']))
                conn.putheader('offset', str(headers['offset']))
                conn.putheader('file_size', str(headers['file_size']))
            elif method == 'POST':
                conn.putheader('Content-Type', 'application/x-www-form-urlencoded')
                conn.putheader('Content-Length', str(len(payload)))
            conn.endheaders()
            if file is not None:
                while chunk := file.read(1024 * 1024):
                    conn.send(chunk)
            elif payload:
                conn.send(payload)
            response = conn.getresponse()
            data = response.read(1024 * 1024 + 1)
            if response.status != 200 or len(data) > 1024 * 1024:
                raise MetaHTTPError(f'Meta request failed (HTTP {response.status})')
            try:
                result = json.loads(data)
            except (ValueError, UnicodeDecodeError) as exc:
                raise MetaHTTPError('Invalid Meta response') from exc
            if not isinstance(result, dict) or 'error' in result:
                raise MetaHTTPError('Meta returned an error')
            return result
        finally:
            conn.close()
