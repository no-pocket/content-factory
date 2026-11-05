"""Only route model requests to approved local services."""

import os
from urllib.parse import urlparse


def local_model_url(backend: str) -> str | None:
    if backend == "kepler_gpu":
        url = os.getenv("KEPLER_BRIDGE_URL", "http://kepler-bridge:11434").rstrip("/")
        hosts = {"kepler-bridge", "localhost", "127.0.0.1", "host.docker.internal"}
    elif backend == "ollama":
        url = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
        hosts = {"ollama", "localhost", "127.0.0.1", "host.docker.internal"}
    else:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in hosts or parsed.port not in (None, 11434):
        return None
    return url


def require_complete_reply(reply: dict) -> None:
    """Reject model decisions made from incomplete input or output."""
    if reply.get('prompt_truncated'):
        raise ValueError('Model prompt was truncated')
    reason = reply.get('done_reason')
    if reason is not None and reason != 'stop':
        raise ValueError(f'Model response ended with {reason}')
