from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Callable, Mapping
from urllib.parse import urlparse
import urllib.error
import urllib.request

from fap_media_generation import GenerationRequest, MediaArtifact


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineConfig:
    engine_id: str
    media_type: str
    endpoint: str
    token_env: str
    timeout_s: float = 60.0
    max_bytes: int = 64 * 1024 * 1024
    max_polls: int = 40
    poll_interval_s: float = 0.5

    def validate(self) -> None:
        if not self.engine_id or len(self.engine_id) > 120:
            raise ValueError("engine_id invalid")
        if self.media_type not in {"image", "video"}:
            raise ValueError("media_type invalid")
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("endpoint must be credential-free HTTPS")
        if not self.token_env or any(
            ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in self.token_env
        ):
            raise ValueError("token_env invalid")
        if not (1.0 <= self.timeout_s <= 300.0):
            raise ValueError("timeout_s out of bounds")
        if not (1024 <= self.max_bytes <= 512 * 1024 * 1024):
            raise ValueError("max_bytes out of bounds")
        if not (0 <= self.max_polls <= 240):
            raise ValueError("max_polls out of bounds")
        if not (0.0 <= self.poll_interval_s <= 10.0):
            raise ValueError("poll_interval_s out of bounds")


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float, int], TransportResponse]


def _default_transport(method, url, headers, body, timeout_s, max_bytes):
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            data = response.read(max_bytes + 1)
            return TransportResponse(
                int(getattr(response, "status", 200)),
                dict(response.headers.items()),
                data,
            )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EngineError("media engine transport failed") from exc


class HTTPMediaEngine:
    """HTTPS image/video engine with synchronous or bounded async job support.

    Provider responses:
      completed: {"status":"completed","mime_type":"image/png","data_base64":"..."}
      async:     {"status":"queued","job_id":"...","poll_url":"https://same-origin/..."}

    Polling is same-origin only. Credentials come from a named environment variable
    and are never persisted into registry/config output.
    """

    def __init__(
        self,
        config: EngineConfig,
        *,
        artifact_dir: str | Path,
        transport: Transport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        config.validate()
        self.config = config
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.transport = transport or _default_transport
        self.sleep_fn = sleep_fn

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != self.config.media_type:
            raise EngineError("request media type does not match engine")
        token = os.environ.get(self.config.token_env)
        if not token:
            raise EngineError("media engine credential unavailable")

        payload = {
            "prompt": prompt,
            "media_type": request.media_type,
            "width": request.width,
            "height": request.height,
            "duration_s": request.duration_s,
            "fps": request.fps,
            "constraints": list(request.constraints),
        }
        if previous is not None:
            payload["previous_digest"] = previous.digest
        if critique is not None:
            payload["repair_issues"] = [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "repair_hint": issue.repair_hint or issue.detail,
                }
                for issue in critique.issues[:12]
            ]

        headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = self.transport(
            "POST",
            self.config.endpoint,
            headers,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            self.config.timeout_s,
            self.config.max_bytes,
        )
        result = self._decode_response(response)
        polls = 0
        while result.get("status") in {"queued", "running", "processing"}:
            if polls >= self.config.max_polls:
                raise EngineError("media engine poll budget exhausted")
            poll_url = str(result.get("poll_url", ""))
            self._validate_poll_url(poll_url)
            if self.config.poll_interval_s:
                self.sleep_fn(self.config.poll_interval_s)
            response = self.transport(
                "GET",
                poll_url,
                {"Authorization": "Bearer " + token, "Accept": "application/json"},
                None,
                self.config.timeout_s,
                self.config.max_bytes,
            )
            result = self._decode_response(response)
            polls += 1

        if result.get("status") != "completed":
            raise EngineError("media engine did not complete successfully")
        return self._persist_completed(result, polls)

    def _decode_response(self, response: TransportResponse) -> dict:
        if response.status < 200 or response.status >= 300:
            raise EngineError("media engine returned non-success status")
        if len(response.body) > self.config.max_bytes:
            raise EngineError("media engine response exceeds byte limit")
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EngineError("media engine response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise EngineError("media engine response schema invalid")
        return value

    def _validate_poll_url(self, poll_url: str) -> None:
        source = urlparse(self.config.endpoint)
        target = urlparse(poll_url)
        if (
            target.scheme != "https"
            or target.netloc != source.netloc
            or target.username
            or target.password
        ):
            raise EngineError("poll_url must be credential-free HTTPS on engine origin")

    def _persist_completed(self, result: dict, polls: int) -> MediaArtifact:
        mime = result.get("mime_type")
        encoded = result.get("data_base64")
        expected_prefix = "image/" if self.config.media_type == "image" else "video/"
        if not isinstance(mime, str) or not mime.startswith(expected_prefix):
            raise EngineError("completed artifact MIME mismatch")
        if not isinstance(encoded, str):
            raise EngineError("completed artifact data_base64 missing")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception as exc:
            raise EngineError("completed artifact base64 invalid") from exc
        if not data or len(data) > self.config.max_bytes:
            raise EngineError("completed artifact size invalid")

        digest = sha256(data).hexdigest()
        suffix = self._suffix_for_mime(mime)
        destination = self.artifact_dir / f"{digest}{suffix}"
        if not destination.exists():
            fd, tmp = tempfile.mkstemp(prefix=digest + ".", dir=str(self.artifact_dir))
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, destination)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

        return MediaArtifact(
            media_type=self.config.media_type,
            digest=digest,
            mime_type=mime,
            locator=str(destination),
            metadata={
                "engine_id": self.config.engine_id,
                "bytes": len(data),
                "polls": polls,
                "engine_status": "completed",
            },
        )

    @staticmethod
    def _suffix_for_mime(mime: str) -> str:
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
        }
        return mapping.get(mime, ".bin")
