from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


SUPPORTED_MEDIA = {"image", "video"}


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    media_type: str = "image"
    width: int = 1024
    height: int = 1024
    duration_s: float = 0.0
    fps: int = 0
    max_attempts: int = 4
    min_score: float = 0.90
    constraints: tuple[str, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt is required")
        if self.media_type not in SUPPORTED_MEDIA:
            raise ValueError("unsupported media_type")
        if not (64 <= self.width <= 4096 and 64 <= self.height <= 4096):
            raise ValueError("image dimensions out of bounds")
        if not (1 <= self.max_attempts <= 8):
            raise ValueError("max_attempts out of bounds")
        if not (0.0 <= self.min_score <= 1.0):
            raise ValueError("min_score out of bounds")
        if len(self.constraints) > 32 or any(len(x) > 500 for x in self.constraints):
            raise ValueError("constraints out of bounds")
        if self.media_type == "image":
            if self.duration_s != 0.0 or self.fps != 0:
                raise ValueError("image requests must not set duration/fps")
        else:
            if not (0.1 <= self.duration_s <= 120.0):
                raise ValueError("video duration out of bounds")
            if not (1 <= self.fps <= 120):
                raise ValueError("video fps out of bounds")


@dataclass(frozen=True)
class MediaArtifact:
    media_type: str
    digest: str
    mime_type: str
    locator: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.media_type not in SUPPORTED_MEDIA:
            raise ValueError("artifact media_type invalid")
        if not isinstance(self.digest, str) or len(self.digest.strip()) < 4:
            raise ValueError("artifact digest required")
        expected = "image/" if self.media_type == "image" else "video/"
        if not isinstance(self.mime_type, str) or not self.mime_type.startswith(expected):
            raise ValueError("artifact MIME does not match media type")


@dataclass(frozen=True)
class CritiqueIssue:
    code: str
    detail: str
    severity: str = "medium"
    repair_hint: str = ""

    def validate(self) -> None:
        if not self.code:
            raise ValueError("issue code required")
        if self.severity not in {"low", "medium", "high", "fatal"}:
            raise ValueError("unsupported issue severity")
        if len(self.detail) > 1200 or len(self.repair_hint) > 1200:
            raise ValueError("issue text too long")


@dataclass(frozen=True)
class Critique:
    score: float
    issues: tuple[CritiqueIssue, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not (0.0 <= float(self.score) <= 1.0):
            raise ValueError("critique score out of bounds")
        if len(self.issues) > 64:
            raise ValueError("too many critique issues")
        for issue in self.issues:
            issue.validate()

    @property
    def has_fatal(self) -> bool:
        return any(issue.severity == "fatal" for issue in self.issues)


@dataclass(frozen=True)
class GenerationStep:
    attempt: int
    prompt: str
    artifact: MediaArtifact
    critique: Critique


@dataclass(frozen=True)
class GenerationResult:
    status: str
    best_artifact: MediaArtifact | None
    best_score: float
    steps: tuple[GenerationStep, ...]
    stop_reason: str

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


class MediaGenerator(Protocol):
    def generate(
        self,
        request: GenerationRequest,
        *,
        prompt: str,
        previous: MediaArtifact | None,
        critique: Critique | None,
    ) -> MediaArtifact: ...


class MediaCritic(Protocol):
    def critique(self, request: GenerationRequest, artifact: MediaArtifact) -> Critique: ...
