from __future__ import annotations

from dataclasses import dataclass

import pytest

from fap_media_generation import (
    Critique,
    CritiqueIssue,
    GenerationRequest,
    MediaArtifact,
)
from fap_observed_media import (
    CompositeCritic,
    ObservationEnvelope,
    ObservationError,
    ObserverBinding,
    ObservedMediaGenerator,
    build_observed_generation_controller,
)


class Generator:
    def __init__(self, media_type="video"):
        self.media_type = media_type
        self.calls = 0

    def generate(self, request, *, prompt, previous, critique):
        self.calls += 1
        mime = "video/mp4" if self.media_type == "video" else "image/png"
        return MediaArtifact(
            self.media_type,
            f"d{self.calls:03d}",
            mime,
            locator=f"artifact://{self.calls}",
            metadata={"origin": "generator"},
        )


class TemporalObserver:
    def __init__(self, *, mismatched=False):
        self.mismatched = mismatched

    def observe(self, request, artifact):
        digest = "wrong" if self.mismatched else artifact.digest
        return ObservationEnvelope(
            digest,
            {
                "frames": [
                    {
                        "index": 0,
                        "timestamp_s": 0.0,
                        "width": 64,
                        "height": 64,
                        "luminance": 0.5,
                        "tracks": [],
                    },
                    {
                        "index": 1,
                        "timestamp_s": 1.0,
                        "width": 64,
                        "height": 64,
                        "luminance": 0.5,
                        "tracks": [],
                    },
                ],
                "expected_ids": [],
            },
            observer_id="temporal-observer.v1",
            evidence_kind="temporal",
        )


class ScoreCritic:
    def __init__(self, score, *, fatal=False):
        self.score = score
        self.fatal = fatal

    def critique(self, request, artifact):
        issues = ()
        if self.fatal:
            issues = (CritiqueIssue("fatal", "bad evidence", "fatal"),)
        return Critique(self.score, issues, evidence={"score": self.score})


def test_observer_evidence_is_attached_and_digest_bound():
    wrapped = ObservedMediaGenerator(
        Generator(),
        [ObserverBinding("temporal_evidence", TemporalObserver(), ("video",))],
    )
    artifact = wrapped.generate(
        GenerationRequest(
            "video",
            media_type="video",
            duration_s=2.0,
            fps=24,
        ),
        prompt="video",
        previous=None,
        critique=None,
    )
    assert "temporal_evidence" in artifact.metadata
    manifest = artifact.metadata["observation_manifest"]["temporal_evidence"]
    assert manifest["artifact_digest"] == artifact.digest
    assert manifest["observer_id"] == "temporal-observer.v1"


def test_stale_evidence_digest_fails_closed():
    wrapped = ObservedMediaGenerator(
        Generator(),
        [ObserverBinding("temporal_evidence", TemporalObserver(mismatched=True), ("video",))],
    )
    with pytest.raises(ObservationError):
        wrapped.generate(
            GenerationRequest("video", media_type="video", duration_s=2.0, fps=24),
            prompt="video",
            previous=None,
            critique=None,
        )


def test_observer_can_be_media_type_scoped():
    wrapped = ObservedMediaGenerator(
        Generator(media_type="image"),
        [ObserverBinding("temporal_evidence", TemporalObserver(), ("video",))],
    )
    with pytest.raises(ObservationError):
        wrapped.generate(
            GenerationRequest("image"),
            prompt="image",
            previous=None,
            critique=None,
        )


def test_duplicate_metadata_keys_are_rejected():
    with pytest.raises(ValueError):
        ObservedMediaGenerator(
            Generator(),
            [
                ObserverBinding("evidence", TemporalObserver()),
                ObserverBinding("evidence", TemporalObserver()),
            ],
        )


def test_composite_critic_uses_minimum_score():
    result = CompositeCritic([ScoreCritic(0.95), ScoreCritic(0.72)]).critique(None, object())
    assert result.score == 0.72
    assert "critic_0" in result.evidence
    assert "critic_1" in result.evidence


def test_composite_fatal_forces_zero():
    result = CompositeCritic([ScoreCritic(0.99), ScoreCritic(0.98, fatal=True)]).critique(None, object())
    assert result.score == 0.0
    assert result.has_fatal


def test_end_to_end_controller_observes_every_attempt():
    generator = Generator()

    class ImprovingCritic:
        def critique(self, request, artifact):
            score = 0.6 if artifact.digest == "d001" else 0.95
            issues = ()
            if score < request.min_score:
                issues = (
                    CritiqueIssue(
                        "temporal",
                        "temporal inconsistency",
                        "high",
                        "stabilize the subject across frames",
                    ),
                )
            return Critique(score, issues, evidence={"digest": artifact.digest})

    controller = build_observed_generation_controller(
        generator,
        observers=[
            ObserverBinding(
                "temporal_evidence",
                TemporalObserver(),
                ("video",),
            )
        ],
        critics=[ImprovingCritic()],
    )
    result = controller.run(
        GenerationRequest(
            "dog running",
            media_type="video",
            duration_s=3.0,
            fps=24,
            max_attempts=3,
            min_score=0.9,
        )
    )
    assert result.accepted
    assert len(result.steps) == 2
    assert generator.calls == 2
    for step in result.steps:
        assert (
            step.artifact.metadata["observation_manifest"]["temporal_evidence"]["artifact_digest"]
            == step.artifact.digest
        )


def test_original_generator_metadata_is_preserved():
    wrapped = ObservedMediaGenerator(
        Generator(),
        [ObserverBinding("temporal_evidence", TemporalObserver(), ("video",))],
    )
    artifact = wrapped.generate(
        GenerationRequest("video", media_type="video", duration_s=1.0, fps=24),
        prompt="video",
        previous=None,
        critique=None,
    )
    assert artifact.metadata["origin"] == "generator"
