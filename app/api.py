"""Authenticated local HTTP v1 adapter. Business rules live in service.py."""
from __future__ import annotations

import base64
import binascii
import hmac
import io
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import service, store
from .editorial import summarize

MAX_BODY = 64 * 1024 * 1024
MAX_UPLOAD_BODY = 2 * 1024 * 1024 * 1024


class UploadReader:
    """Expose exactly Content-Length bytes without buffering the full video."""
    def __init__(self, stream, size: int):
        self.stream, self.remaining = stream, size

    def read(self, size: int = -1) -> bytes:
        if not self.remaining:
            return b''
        requested = min(self.remaining, size if size >= 0 else 65536)
        try:
            data = self.stream.read(requested)
        except OSError as exc:
            raise ValueError('Upload body read failed') from exc
        if not data:
            raise ValueError('Incomplete upload body')
        self.remaining -= len(data)
        return data


def public_job(job: dict) -> dict:
    result = {k: v for k, v in job.items() if k not in {'source', 'retry_candidate'}}
    result['candidates'] = [{k: v for k, v in c.items() if k not in {'file', 'timeline_file'}}
                            for c in job.get('candidates', [])]
    result['api_version'] = '1'
    return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _json(self, status: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def _dispatch(self):
        token = os.getenv('CONTENT_FACTORY_API_TOKEN', '')
        if not token or not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
            return self._json(401, {'error': {'code': 'unauthorized', 'message': 'Bearer token required'}})
        # No cookie authentication, no CORS, no browser Origin accepted for mutations.
        if self.command == 'POST' and self.headers.get('Origin'):
            raise PermissionError('Browser origins are not enabled')
        path = urlsplit(self.path).path.strip('/').split('/')
        if path[:2] == ['v2', 'jobs']:
            if len(path) == 3 and self.command == 'GET':
                job = store.load(path[2])
                result = public_job(job)
                result.update(api_version='2', editorial=service.get_editorial_view(job))
                return self._json(200, result)
            if len(path) == 6 and path[3] == 'candidates' and path[5] == 'reviews' and self.command == 'POST':
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError('Content-Type application/json required')
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    raise ValueError('Provide one Content-Length')
                size = int(self.headers['Content-Length'])
                if not 0 < size <= 65536:
                    return self._json(413, {'error': {'code': 'body_limit', 'message': 'Review must be 1..64 KiB'}})
                request = json.loads(self.rfile.read(size))
                return self._json(200, service.review_candidate_v2(path[2], path[4], request, channel='api'))
            return self._json(404, {'error': {'code': 'not_found', 'message': 'Unknown v2 route'}})
        if path[:2] == ['v1', 'metrics'] and len(path) == 2 and self.command == 'GET':
            return self._json(200, summarize(store.all_jobs()))
        if path[:2] != ['v1', 'jobs']:
            return self._json(404, {'error': {'code': 'not_found', 'message': 'Unknown route'}})
        if path == ['v1', 'jobs', 'upload'] and self.command == 'POST':
            if self.headers.get_content_type() != 'application/octet-stream':
                raise ValueError('Content-Type application/octet-stream required')
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                raise ValueError('Provide one Content-Length; chunked uploads are not supported')
            size = int(self.headers['Content-Length'])
            if not 0 < size <= MAX_UPLOAD_BODY:
                return self._json(413, {'error': {'code': 'body_limit', 'message': 'Video must be 1 byte..2 GiB'}})
            encoded = self.headers.get('X-Content-Factory-Metadata', '')
            if len(encoded) > 48 * 1024:
                raise ValueError('Upload metadata header too large')
            metadata = json.loads(base64.b64decode(encoded, validate=True).decode('utf-8'))
            if not isinstance(metadata, dict) or 'source_url' in metadata or 'upload_base64' in metadata:
                raise ValueError('Raw upload requires object metadata without source_url/upload_base64')
            job = service.create_job(metadata, upload=UploadReader(self.rfile, size), filename=metadata.get('filename'))
            return self._json(201, public_job(job))
        body = None
        if self.command == 'POST':
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('Content-Type application/json required')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self._json(413, {'error': {'code': 'body_limit', 'message': 'Body must be 1..64 MiB'}})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('JSON object required')
        if len(path) == 2:
            if self.command == 'GET':
                return self._json(200, {'api_version': '1', 'jobs': [public_job(j) for j in store.all_jobs()]})
            upload = None
            if 'upload_base64' in body:
                try:
                    upload = io.BytesIO(base64.b64decode(body['upload_base64'], validate=True))
                except (ValueError, TypeError, binascii.Error) as exc:
                    raise ValueError('Invalid upload_base64') from exc
            job = service.create_job(body, upload=upload, filename=body.get('filename'))
            return self._json(201, public_job(job))
        jid = path[2]
        if len(path) == 3 and self.command == 'GET':
            return self._json(200, public_job(store.load(jid)))
        if len(path) == 4 and self.command == 'POST':
            if path[3] == 'review':
                job = service.review_job(jid, body.get('decisions'), expected_revision=body.get('expected_revision'))
            elif path[3] == 'retry-enqueue':
                job = service.retry_enqueue(jid)
            elif path[3] == 'verify':
                job = service.verify_existing(jid)
            elif path[3] == 'reject':
                job = service.reject_job(jid, body.get('reason'), origin='api')
            else:
                return self._json(404, {'error': {'code': 'not_found', 'message': 'Unknown operation'}})
            return self._json(200, public_job(job))
        if len(path) == 6 and path[3] == 'candidates' and path[5] == 'retry' and self.command == 'POST':
            return self._json(202, public_job(service.retry_candidate(jid, int(path[4]))))
        if len(path) == 6 and path[3] == 'candidates' and path[5] == 'review' and self.command == 'POST':
            job = service.review_candidate(jid, int(path[4]), body.get('decision'), body.get('reason'),
                                            expected_revision=body.get('expected_revision'), ratings=body.get('ratings'),
                                            rework=body.get('rework', False), adjustments=body.get('adjustments', ''))
            return self._json(200, public_job(job))
        if len(path) == 7 and path[3] == 'candidates' and path[5] == 'media' and self.command == 'GET':
            job = store.load(jid)
            index = int(path[4])
            kind = path[6]
            if not 0 <= index < len(job['candidates']) or kind not in {'mp4', 'webm', 'timeline'}:
                raise ValueError('Invalid artifact')
            if job['status'] not in {'NEEDS_REVIEW', 'PARTIAL_FAILED', 'APPROVED', 'REJECTED'}:
                raise service.Conflict('Job is processing')
            if not service.verify_reviewable(job, index):
                raise service.Conflict('Candidate requires technical verification')
            suffix, mime = {'mp4': ('.mp4', 'video/mp4'), 'webm': ('.preview.webm', 'video/webm'),
                            'timeline': ('.timeline.json', 'application/json')}[kind]
            clip = job['candidates'][index]
            target = (Path(clip['file']).with_suffix(suffix) if job.get('editorial_protocol') == 2 else
                      store.OUTPUT / jid / f'candidate_{index+1}{suffix}').resolve()
            if not target.is_relative_to(store.OUTPUT.resolve()):
                raise ValueError('Invalid path')
            with target.open('rb') as handle:
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(target.stat().st_size))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                import shutil
                shutil.copyfileobj(handle, self.wfile)
            return
        self._json(404, {'error': {'code': 'not_found', 'message': 'Unknown route'}})

    def _handle(self):
        self.connection.settimeout(30)
        try:
            self._dispatch()
        except service.Conflict as exc:
            self._json(409, {'error': {'code': 'editorial_protocol_required' if str(exc) == 'editorial_protocol_required' else 'conflict', 'message': str(exc)}})
        except FileNotFoundError:
            self._json(404, {'error': {'code': 'not_found', 'message': 'Job or artifact not found'}})
        except PermissionError as exc:
            self._json(403, {'error': {'code': 'permission_required', 'message': str(exc)}})
        except (ValueError, TypeError, KeyError) as exc:
            self._json(422, {'error': {'code': 'invalid_request', 'message': str(exc)}})
        except RuntimeError as exc:
            self._json(503, {'error': {'code': 'unavailable', 'message': str(exc)}})
        except Exception:
            logging.exception('API request failed')
            self._json(500, {'error': {'code': 'internal_error', 'message': 'See local service logs'}})

    do_GET = _handle
    do_POST = _handle


def main():
    if len(os.getenv('CONTENT_FACTORY_API_TOKEN', '')) < 24:
        raise SystemExit('Set CONTENT_FACTORY_API_TOKEN with at least 24 characters')
    # Container binds internally; Compose only publishes localhost. Direct use defaults loopback.
    server = HTTPServer((os.getenv('CONTENT_FACTORY_API_BIND', '127.0.0.1'), 8510), Handler)
    server.serve_forever()


if __name__ == '__main__':
    main()
