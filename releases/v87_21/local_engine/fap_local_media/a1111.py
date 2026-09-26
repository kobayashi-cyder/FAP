from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Mapping
from urllib.parse import urlparse
import urllib.error
import urllib.request

from fap_media_generation import GenerationRequest, MediaArtifact


class LocalEngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalTransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


LocalTransport = Callable[
    [str, str, Mapping[str, str], bytes | None, float, int],
    LocalTransportResponse,
]


def _transport(method, url, headers, body, timeout_s, max_bytes):
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            data = response.read(max_bytes + 1)
            return LocalTransportResponse(
                int(getattr(response, "status", 200)),
                dict(response.headers.items()),
                data,
            )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LocalEngineError("local image engine transport failed") from exc


def _normalize_loopback_base(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("local engine must use http or https")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("local engine must use a loopback host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("local engine URL must not contain credentials/query/fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("local engine base URL must not contain a path")
    return raw


@dataclass(frozen=True)
class A1111Probe:
    engine_id: str
    base_url: str
    model_count: int
    model_titles: tuple[str, ...]


class A1111LocalEngine:
    """Loopback-only AUTOMATIC1111 / Forge-compatible txt2img adapter."""

    def __init__(
        self,
        base_url: str,
        *,
        artifact_dir: str | Path,
        engine_id: str | None = None,
        timeout_s: float = 180.0,
        max_bytes: int = 64 * 1024 * 1024,
        transport: LocalTransport | None = None,
    ):
        self.base_url = _normalize_loopback_base(base_url)
        parsed = urlparse(self.base_url)
        self.engine_id = engine_id or f"a1111-local-{parsed.hostname}-{parsed.port or 80}"
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = float(timeout_s)
        self.max_bytes = int(max_bytes)
        self.transport = transport or _transport

    def probe(self, timeout_s: float = 1.0) -> A1111Probe:
        response = self.transport(
            "GET",
            self.base_url + "/sdapi/v1/sd-models",
            {"Accept": "application/json"},
            None,
            float(timeout_s),
            2 * 1024 * 1024,
        )
        if response.status < 200 or response.status >= 300:
            raise LocalEngineError("A1111 model probe returned non-success status")
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalEngineError("A1111 model probe returned invalid JSON") from exc
        if not isinstance(value, list):
            raise LocalEngineError("A1111 model probe schema invalid")
        titles = []
        for row in value[:64]:
            if isinstance(row, dict):
                title = str(row.get("title") or row.get("model_name") or "").strip()
                if title:
                    titles.append(title)
        return A1111Probe(
            self.engine_id,
            self.base_url,
            len(value),
            tuple(titles),
        )

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != "image":
            raise LocalEngineError("A1111 local adapter supports image generation only")

        payload = {
            "prompt": prompt,
            "steps": int(os.environ.get("FAP_A1111_STEPS", "20")),
            "width": request.width,
            "height": request.height,
            "batch_size": 1,
            "n_iter": 1,
        }
        negative = os.environ.get("FAP_A1111_NEGATIVE_PROMPT", "").strip()
        if negative:
            payload["negative_prompt"] = negative

        response = self.transport(
            "POST",
            self.base_url + "/sdapi/v1/txt2img",
            {"Content-Type": "application/json", "Accept": "application/json"},
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            self.timeout_s,
            self.max_bytes,
        )
        if response.status < 200 or response.status >= 300:
            raise LocalEngineError("A1111 txt2img returned non-success status")
        if len(response.body) > self.max_bytes:
            raise LocalEngineError("A1111 response exceeds byte limit")
        try:
            value = json.loads(response.body.decode("utf-8"))
            images = value["images"]
            encoded = images[0]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
            raise LocalEngineError("A1111 txt2img response schema invalid") from exc
        if not isinstance(encoded, str):
            raise LocalEngineError("A1111 image payload invalid")
        if "," in encoded and encoded.lstrip().startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception as exc:
            raise LocalEngineError("A1111 image base64 invalid") from exc
        if not data or len(data) > self.max_bytes:
            raise LocalEngineError("A1111 image size invalid")

        digest = sha256(data).hexdigest()
        destination = self.artifact_dir / f"{digest}.png"
        if not destination.exists():
            fd, tmp = tempfile.mkstemp(prefix=digest + ".", dir=str(self.artifact_dir))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, destination)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(destination),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "a1111-local",
                "base_url": self.base_url,
                "bytes": len(data),
                "engine_status": "completed",
            },
        )


class A1111Discovery:
    DEFAULTS = (
        "http://127.0.0.1:7860",
        "http://127.0.0.1:7861",
        "http://localhost:7860",
    )

    def __init__(
        self,
        *,
        artifact_dir: str | Path,
        transport: LocalTransport | None = None,
        candidates: tuple[str, ...] | None = None,
    ):
        self.artifact_dir = Path(artifact_dir)
        self.transport = transport
        self.candidates = candidates or self._environment_candidates()

    def _environment_candidates(self) -> tuple[str, ...]:
        raw = os.environ.get("FAP_LOCAL_IMAGE_ENGINES", "").strip()
        values = (
            tuple(x.strip() for x in raw.split(",") if x.strip())
            if raw
            else self.DEFAULTS
        )
        normalized = []
        for value in values:
            try:
                base = _normalize_loopback_base(value)
            except ValueError:
                continue
            if base not in normalized:
                normalized.append(base)
        return tuple(normalized)

    def discover(self) -> list[tuple[A1111LocalEngine, A1111Probe]]:
        found = []
        for index, base in enumerate(self.candidates, start=1):
            try:
                engine = A1111LocalEngine(
                    base,
                    artifact_dir=self.artifact_dir,
                    engine_id=f"a1111-local-{index}",
                    transport=self.transport,
                )
                probe = engine.probe(timeout_s=1.0)
            except Exception:
                continue
            found.append((engine, probe))
        return found
