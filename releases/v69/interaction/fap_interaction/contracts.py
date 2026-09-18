from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


@dataclass(frozen=True)
class MediaArtifact:
    kind: str
    mime_type: str
    data: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_hex(self.data)

    def require(self, *, kind: str, mime_prefix: str) -> "MediaArtifact":
        if self.kind != kind:
            raise ValueError(f"artifact kind must be {kind}")
        if not isinstance(self.data, (bytes, bytearray)) or not self.data:
            raise ValueError("artifact data must be non-empty bytes")
        if not self.mime_type.startswith(mime_prefix):
            raise ValueError(f"artifact MIME must start with {mime_prefix}")
        return self


@dataclass(frozen=True)
class SkillDecision:
    status: str
    reason: str
    artifact: Optional[MediaArtifact] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"ok", "needs_provider", "rejected"}:
            raise ValueError("invalid status")
