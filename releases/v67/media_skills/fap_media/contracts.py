from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import hashlib

SUPPORTED_IMAGE_FORMATS = {"png", "jpeg", "webp"}
SUPPORTED_VIDEO_FORMATS = {"mp4", "webm"}
SUPPORTED_AUDIO_FORMATS = {"pcm16", "wav"}

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class MediaArtifact:
    kind: str
    mime_type: str
    data: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return sha256_hex(self.data)

    def require_nonempty(self) -> "MediaArtifact":
        if not isinstance(self.data, (bytes, bytearray)) or not self.data:
            raise ValueError("artifact data must be non-empty bytes")
        return self

@dataclass(frozen=True)
class SkillDecision:
    status: str
    reason: str
    artifact: Optional[MediaArtifact] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in {"ok", "needs_provider", "rejected"}:
            raise ValueError("invalid status")
