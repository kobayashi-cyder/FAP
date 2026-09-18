"""Privacy-safe evidence for image-provider probes. No prompts, secrets, or raw media."""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Optional

_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}

@dataclass(frozen=True)
class ImageEvidence:
    adapter: str
    provider: str
    outcome: str
    mime: Optional[str]
    width: Optional[int]
    height: Optional[int]
    byte_count: int
    sha256: Optional[str]
    latency_ms: float
    peak_rss_delta_bytes: Optional[int] = None
    retained_storage_bytes: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def record_success(*, adapter: str, provider: str, mime: str, width: int, height: int,
                   payload: bytes, latency_ms: float, max_bytes: int = 16 * 1024 * 1024,
                   max_width: int = 4096, max_height: int = 4096,
                   peak_rss_delta_bytes: Optional[int] = None) -> ImageEvidence:
    if not adapter or not provider:
        raise ValueError("adapter/provider required")
    if mime not in _ALLOWED_MIME:
        raise ValueError("unsupported MIME")
    if not (1 <= width <= max_width and 1 <= height <= max_height):
        raise ValueError("dimensions out of bounds")
    if not payload or len(payload) > max_bytes:
        raise ValueError("payload size out of bounds")
    if latency_ms < 0:
        raise ValueError("latency must be measured and non-negative")
    return ImageEvidence(adapter, provider, "validated", mime, width, height, len(payload),
                         hashlib.sha256(payload).hexdigest(), latency_ms,
                         peak_rss_delta_bytes, 0)


def record_failure(*, adapter: str, provider: str, outcome: str, latency_ms: float) -> ImageEvidence:
    if not adapter or not provider or not outcome or outcome == "validated":
        raise ValueError("explicit failure identity/outcome required")
    if latency_ms < 0:
        raise ValueError("latency must be non-negative")
    return ImageEvidence(adapter, provider, outcome, None, None, None, 0, None, latency_ms, None, 0)
