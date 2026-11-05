"""Local Ollama-compatible adapter for a CUDA 10.2 llama.cpp server."""

from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


MODEL_NAME = re.compile(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]+\Z")
SUPPORTED_OPTIONS = {'temperature', 'num_predict', 'num_ctx'}


class ContextBudgetError(ValueError):
    """The GPU request cannot fit without losing input or response capacity."""


def resolve_model_blob(root: Path, model: str) -> Path:
    if not MODEL_NAME.fullmatch(model):
        raise ValueError("Invalid Ollama model name")
    name, tag = model.split(":", 1)
    manifest = root / "manifests" / "registry.ollama.ai" / "library" / name / tag
    data = json.loads(manifest.read_text(encoding="utf-8"))
    layer = next((item for item in data["layers"] if item.get("mediaType") == "application/vnd.ollama.image.model"), None)
    if layer is None or not SHA256.fullmatch(layer.get("digest", "")):
        raise ValueError("Ollama manifest has no valid model blob")
    blob = root / "blobs" / layer["digest"].replace(":", "-", 1)
    if not blob.is_file():
        raise FileNotFoundError(blob)
    return blob


def qwen_chat_prompt(prompt: str) -> str:
    """The single-user ChatML form used by llama.cpp b4300 for Qwen 2.5."""
    return f'<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n'


def check_context_budget(prompt_tokens: int, max_tokens: int, server_context: int,
                         *, requested_context: int | None = None, margin: int = 16) -> int:
    """Reject requests that the fixed-size GPU context cannot hold intact."""
    if any(type(value) is not int or value < 0 for value in (prompt_tokens, max_tokens, server_context, margin)):
        raise ValueError('Invalid context budget values')
    if server_context < 32 or max_tokens < 1:
        raise ValueError('Invalid context window or response reserve')
    if requested_context is not None:
        if type(requested_context) is not int or requested_context < 32:
            raise ValueError('Invalid requested context')
        if requested_context > server_context:
            raise ContextBudgetError(f'Requested context {requested_context} exceeds GPU context {server_context}')
    limit = requested_context or server_context
    if prompt_tokens + max_tokens + margin > limit:
        raise ContextBudgetError(f'GPU context exceeded: prompt={prompt_tokens}, response={max_tokens}, '
                                 f'margin={margin}, window={limit}')
    return limit


def preflight_context(engine: str, prompt: str, max_tokens: int, *,
                      requested_context: int | None = None, margin: int = 16) -> tuple[int, int]:
    """Count the actual Qwen ChatML prompt using the running server's tokenizer."""
    with urllib.request.urlopen(engine + '/props', timeout=5) as response:
        props = json.load(response)
    template = props.get('chat_template', '')
    if '<|im_start|>' not in template or '<|im_end|>' not in template:
        raise ValueError('Unsupported chat template for GPU context accounting')
    server_context = props['default_generation_settings']['n_ctx']
    request = urllib.request.Request(
        engine + '/tokenize',
        data=json.dumps({'content': qwen_chat_prompt(prompt)}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        tokens = json.load(response)['tokens']
    if not isinstance(tokens, list) or not all(type(token) is int for token in tokens):
        raise ValueError('GPU tokenizer returned invalid tokens')
    limit = check_context_budget(len(tokens), max_tokens, server_context,
                                 requested_context=requested_context, margin=margin)
    return len(tokens), limit


def translate_generate(body: dict, *, model: str) -> dict:
    if body.get("model") != model:
        raise ValueError(f"Only {model} is loaded in the Kepler server")
    if body.get("stream", False) is not False or not isinstance(body.get("prompt"), str):
        raise ValueError("A non-streaming text prompt is required")
    options = body.get("options") or {}
    if not isinstance(options, dict):
        raise ValueError('options must be an object')
    unsupported = set(options) - SUPPORTED_OPTIONS
    if unsupported:
        raise ValueError(f'Unsupported Ollama options: {", ".join(sorted(unsupported))}')
    temperature = float(options.get('temperature', 0))
    max_tokens = options.get('num_predict', 350)
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError('temperature must be between 0 and 2')
    if type(max_tokens) is not int or not 1 <= max_tokens <= 2048:
        raise ValueError('num_predict must be an integer from 1 to 2048')
    payload = {
        "messages": [{"role": "user", "content": body["prompt"]}],
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    format_spec = body.get("format")
    if format_spec == "json":
        payload["response_format"] = {"type": "json_object"}
    elif isinstance(format_spec, dict):
        payload["response_format"] = {"type": "json_object", "schema": format_spec}
    elif format_spec not in (None, ""):
        raise ValueError("Unsupported response format")
    return payload


def translate_reply(result: dict, model: str, *, expected_prompt_tokens: int | None = None,
                    context_window: int | None = None) -> dict:
    content = result["choices"][0]["message"]["content"]
    finish_reason = result['choices'][0].get('finish_reason', 'stop')
    usage = result.get("usage", {})
    timings = result.get("timings", {})
    observed_prompt_tokens = usage.get("prompt_tokens", result.get("tokens_evaluated", 0))
    prompt_truncated = (expected_prompt_tokens is not None and observed_prompt_tokens < expected_prompt_tokens)
    return {
        "model": model,
        "response": content,
        "done": True,
        "done_reason": 'prompt_truncated' if prompt_truncated else finish_reason,
        "prompt_truncated": prompt_truncated,
        "context_window": context_window,
        "prompt_eval_count": observed_prompt_tokens,
        "eval_count": usage.get("completion_tokens", result.get("tokens_predicted", 0)),
        "prompt_eval_duration": int(timings.get("prompt_ms", 0) * 1_000_000),
        "eval_duration": int(timings.get("predicted_ms", 0) * 1_000_000),
    }


def run_engine() -> None:
    model = os.getenv("KEPLER_MODEL", "qwen2.5:3b")
    blob = resolve_model_blob(Path(os.getenv("KEPLER_MODELS_DIR", "/models")), model)
    args = [
        "/build/bin/llama-server", "-m", str(blob), "--host", "0.0.0.0", "--port", "8080",
        "--ctx-size", os.getenv("KEPLER_CTX_SIZE", "4096"),
        "--batch-size", os.getenv("KEPLER_BATCH_SIZE", "512"),
        "--ubatch-size", os.getenv("KEPLER_UBATCH_SIZE", "256"),
        "--gpu-layers", os.getenv("KEPLER_GPU_LAYERS", "99"),
        "--threads", os.getenv("KEPLER_THREADS", "4"),
    ]
    os.execv(args[0], args)


def run_bridge() -> None:
    model = os.getenv("KEPLER_MODEL", "qwen2.5:3b")
    engine = os.getenv("KEPLER_ENGINE_URL", "http://kepler-engine:8080").rstrip("/")

    class Handler(BaseHTTPRequestHandler):
        def respond(self, code: int, data: dict) -> None:
            encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            if self.path not in ("/health", "/api/tags", "/api/ps"):
                self.respond(404, {"error": "Not found"})
                return
            try:
                with urllib.request.urlopen(engine + "/health", timeout=2.5) as response:
                    healthy = json.load(response).get("status") == "ok"
            except (OSError, ValueError):
                healthy = False
            if not healthy:
                self.respond(503, {"error": "Kepler model server unavailable"})
            elif self.path == "/health":
                self.respond(200, {"status": "ok", "backend": "cuda10.2"})
            elif self.path == "/api/tags":
                self.respond(200, {"models": [{"name": model}]})
            else:
                try:
                    with urllib.request.urlopen(engine + '/props', timeout=2.5) as response:
                        context_window = json.load(response)['default_generation_settings']['n_ctx']
                    self.respond(200, {"models": [{"name": model, "context_window": context_window,
                                                   "backend": "cuda10.2"}]})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self.respond(503, {'error': f'Kepler model metadata unavailable: {exc}'[:250]})

        def do_POST(self) -> None:
            if self.path != "/api/generate":
                self.respond(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(length))
                payload = translate_generate(body, model=model)
                options = body.get('options') or {}
                prompt_tokens, context_window = preflight_context(
                    engine, body['prompt'], payload['max_tokens'],
                    requested_context=options.get('num_ctx'),
                    margin=int(os.getenv('KEPLER_CONTEXT_MARGIN', '16')))
                request = urllib.request.Request(
                    engine + "/v1/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=int(os.getenv("KEPLER_REQUEST_TIMEOUT", "300"))) as response:
                    result = json.load(response)
                self.respond(200, translate_reply(result, model, expected_prompt_tokens=prompt_tokens,
                                                 context_window=context_window))
            except ContextBudgetError as exc:
                self.respond(422, {'error': str(exc)[:250]})
            except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
                self.respond(503, {"error": str(exc)[:250]})

    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("KEPLER_BRIDGE_PORT", "11434"))), Handler).serve_forever()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("engine", "bridge"):
        raise SystemExit("Usage: python kepler_bridge.py [engine|bridge]")
    (run_engine if sys.argv[1] == "engine" else run_bridge)()
