from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Tuple
from urllib.parse import urlparse


class ImageHTTPError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageResult:
    mime_type: str
    data: bytes
    latency_ms: float


Transport = Callable[[urllib.request.Request, float, int], Tuple[int, Mapping[str, str], bytes]]


def _default_transport(request: urllib.request.Request, timeout_s: float, max_bytes: int):
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            status = int(getattr(response, "status", 200))
            headers = dict(response.headers.items())
            data = response.read(max_bytes + 1)
            return status, headers, data
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ImageHTTPError("image provider transport failed") from exc


class ImageHTTPAdapter:
    """Small synchronous image-provider boundary.

    Secrets are read only from an explicitly named environment variable and are
    never returned in results/errors. Network use is HTTPS-only. This adapter
    deliberately does not claim streaming, retries, provider compatibility, or
    successful real image generation until a real backend is independently exercised.
    """

    def __init__(self, endpoint: str, *, token_env: str, timeout_s: float = 30.0,
                 max_bytes: int = 16 * 1024 * 1024, transport: Transport | None = None):
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("endpoint must be credential-free HTTPS")
        if not token_env or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in token_env):
            raise ValueError("token_env must be an uppercase environment-variable name")
        if timeout_s <= 0 or timeout_s > 120:
            raise ValueError("timeout_s out of bounds")
        if max_bytes <= 0 or max_bytes > 64 * 1024 * 1024:
            raise ValueError("max_bytes out of bounds")
        self.endpoint = endpoint
        self.token_env = token_env
        self.timeout_s = float(timeout_s)
        self.max_bytes = int(max_bytes)
        self.transport = transport or _default_transport

    def generate(self, prompt: str, *, width: int = 1024, height: int = 1024) -> ImageResult:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
            raise ValueError("prompt must contain 1..8000 characters")
        if width < 64 or height < 64 or width > 4096 or height > 4096:
            raise ValueError("image dimensions out of bounds")
        token = os.environ.get(self.token_env)
        if not token:
            raise ImageHTTPError("provider credential unavailable")
        body = json.dumps({"prompt": prompt, "width": int(width), "height": int(height)},
                          separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"})
        start = time.perf_counter()
        status, headers, payload = self.transport(request, self.timeout_s, self.max_bytes)
        latency_ms = (time.perf_counter() - start) * 1000.0
        if status < 200 or status >= 300:
            raise ImageHTTPError("image provider returned non-success status")
        if len(payload) > self.max_bytes:
            raise ImageHTTPError("image provider response exceeds byte limit")
        try:
            response = json.loads(payload.decode("utf-8"))
            mime = response["mime_type"]
            encoded = response["data_base64"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ImageHTTPError("image provider response schema invalid") from exc
        if not isinstance(mime, str) or not mime.startswith("image/"):
            raise ImageHTTPError("image provider MIME invalid")
        if not isinstance(encoded, str):
            raise ImageHTTPError("image provider payload missing")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception as exc:
            raise ImageHTTPError("image provider base64 invalid") from exc
        if not data or len(data) > self.max_bytes:
            raise ImageHTTPError("decoded image size invalid")
        return ImageResult(mime_type=mime, data=data, latency_ms=latency_ms)
