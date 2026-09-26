from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Protocol, Sequence

from fap_media_generation import (
    BoundedMediaGenerationController,
    Critique,
    CritiqueIssue,
    MediaArtifact,
)


class ObservationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservationEnvelope:
    artifact_digest: str
    payload: Any
    observer_id: str = "observer"
    evidence_kind: str = "generic"

    def validate(self) -> None:
        if not isinstance(self.artifact_digest, str) or len(self.artifact_digest.strip()) < 4:
            raise ValueError("observation artifact_digest required")
        if not isinstance(self.observer_id, str) or not self.observer_id.strip():
            raise ValueError("observer_id required")
        if not isinstance(self.evidence_kind, str) or not self.evidence_kind.strip():
            raise ValueError("evidence_kind required")


class MediaObserver(Protocol):
    def observe(self, request, artifact: MediaArtifact) -> ObservationEnvelope: ...


@dataclass(frozen=True)
class ObserverBinding:
    metadata_key: str
    observer: MediaObserver
    media_types: tuple[str, ...] = ("image", "video")

    def validate(self) -> None:
        if not isinstance(self.metadata_key, str) or not self.metadata_key.strip():
            raise ValueError("metadata_key required")
        if not callable(getattr(self.observer, "observe", None)):
            raise TypeError("observer must provide observe()")
        if not self.media_types:
            raise ValueError("media_types must not be empty")
        if any(x not in {"image", "video"} for x in self.media_types):
            raise ValueError("unsupported observer media type")


class ObservedMediaGenerator:
    """Wrap a generator and attach evidence observed from the actual artifact.

    Evidence is accepted only when its digest matches the generated artifact.
    This prevents stale or cross-artifact observations from reaching critics.
    """

    def __init__(self, generator, bindings: Sequence[ObserverBinding]):
        if not callable(getattr(generator, "generate", None)):
            raise TypeError("generator must provide generate()")
        if not bindings:
            raise ValueError("at least one observer binding is required")
        keys: set[str] = set()
        normalized = []
        for binding in bindings:
            binding.validate()
            if binding.metadata_key in keys:
                raise ValueError("duplicate observation metadata_key")
            keys.add(binding.metadata_key)
            normalized.append(binding)
        self.generator = generator
        self.bindings = tuple(normalized)

    def generate(self, request, *, prompt, previous, critique):
        artifact = self.generator.generate(
            request,
            prompt=prompt,
            previous=previous,
            critique=critique,
        )
        artifact.validate()

        metadata = dict(artifact.metadata)
        observation_manifest = dict(metadata.get("observation_manifest", {}))
        for binding in self.bindings:
            if artifact.media_type not in binding.media_types:
                continue
            envelope = binding.observer.observe(request, artifact)
            if not isinstance(envelope, ObservationEnvelope):
                raise ObservationError("observer must return ObservationEnvelope")
            envelope.validate()
            if envelope.artifact_digest != artifact.digest:
                raise ObservationError(
                    f"observation digest mismatch for {binding.metadata_key}"
                )
            metadata[binding.metadata_key] = envelope.payload
            observation_manifest[binding.metadata_key] = {
                "artifact_digest": envelope.artifact_digest,
                "observer_id": envelope.observer_id,
                "evidence_kind": envelope.evidence_kind,
            }

        if not observation_manifest:
            raise ObservationError("no observer evidence produced for generated media")
        metadata["observation_manifest"] = observation_manifest
        return replace(artifact, metadata=metadata)


class CompositeCritic:
    """Fail-closed critic composition.

    A fatal issue from any critic is fatal. Otherwise the minimum score is used,
    so a strong aesthetic score cannot hide a temporal or structural failure.
    """

    def __init__(self, critics: Sequence[Any]):
        if not critics:
            raise ValueError("at least one critic is required")
        for critic in critics:
            if not callable(getattr(critic, "critique", None)):
                raise TypeError("critic must provide critique()")
        self.critics = tuple(critics)

    def critique(self, request, artifact) -> Critique:
        results = []
        for critic in self.critics:
            result = critic.critique(request, artifact)
            if not isinstance(result, Critique):
                raise TypeError("critic must return Critique")
            result.validate()
            results.append(result)

        issues = tuple(issue for result in results for issue in result.issues)
        score = min(float(result.score) for result in results)
        evidence: dict[str, Any] = {}
        for index, result in enumerate(results):
            evidence[f"critic_{index}"] = dict(result.evidence)

        if any(result.has_fatal for result in results):
            score = 0.0
        return Critique(score, issues, evidence=evidence)


def build_observed_generation_controller(
    generator,
    *,
    observers: Sequence[ObserverBinding],
    critics: Sequence[Any],
) -> BoundedMediaGenerationController:
    return BoundedMediaGenerationController(
        ObservedMediaGenerator(generator, observers),
        CompositeCritic(critics),
    )
