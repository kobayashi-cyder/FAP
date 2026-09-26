from __future__ import annotations

import pytest

from fap_media_generation import (
    BoundedMediaGenerationController,
    Critique,
    CritiqueIssue,
    GenerationError,
    GenerationRequest,
    MediaArtifact,
)


class FakeGenerator:
    def __init__(self, sequence, *, media_type="image"):
        self.sequence = list(sequence)
        self.media_type = media_type
        self.calls = []

    def generate(self, request, *, prompt, previous, critique):
        self.calls.append((prompt, previous, critique))
        index = min(len(self.calls) - 1, len(self.sequence) - 1)
        digest, score = self.sequence[index]
        mime = "image/png" if self.media_type == "image" else "video/mp4"
        return MediaArtifact(
            self.media_type,
            digest,
            mime,
            metadata={"score": score},
        )


class FakeCritic:
    def critique(self, request, artifact):
        score = artifact.metadata["score"]
        issues = ()
        if score < request.min_score:
            issues = (
                CritiqueIssue(
                    "composition",
                    "subject placement differs from target",
                    severity="medium",
                    repair_hint="preserve the subject and correct composition",
                ),
            )
        return Critique(score, issues, evidence={"source": "fake-independent-critic"})


def test_image_refines_until_quality_gate():
    generator = FakeGenerator([("a001", 0.41), ("a002", 0.73), ("a003", 0.94)])
    controller = BoundedMediaGenerationController(generator, FakeCritic())
    result = controller.run(GenerationRequest("beagle on a beach", max_attempts=4, min_score=0.9))
    assert result.accepted
    assert result.best_artifact.digest == "a003"
    assert len(result.steps) == 3
    assert "Repair only these verified defects" in generator.calls[1][0]


def test_best_artifact_survives_regression():
    generator = FakeGenerator([("b001", 0.70), ("b002", 0.40), ("b003", 0.62)])
    controller = BoundedMediaGenerationController(generator, FakeCritic())
    result = controller.run(GenerationRequest("product shot", max_attempts=3, min_score=0.95))
    assert result.status == "exhausted"
    assert result.best_artifact.digest == "b001"
    assert result.best_score == 0.70


def test_video_uses_same_bounded_quality_loop():
    generator = FakeGenerator([("v001", 0.55), ("v002", 0.93)], media_type="video")
    controller = BoundedMediaGenerationController(generator, FakeCritic())
    req = GenerationRequest(
        "dog running through surf",
        media_type="video",
        width=1280,
        height=720,
        duration_s=6.0,
        fps=24,
        max_attempts=3,
        min_score=0.9,
    )
    result = controller.run(req)
    assert result.accepted
    assert result.best_artifact.mime_type == "video/mp4"
    assert len(result.steps) == 2


def test_wrong_media_type_fails_closed():
    generator = FakeGenerator([("x001", 0.99)], media_type="video")
    controller = BoundedMediaGenerationController(generator, FakeCritic())
    with pytest.raises(GenerationError):
        controller.run(GenerationRequest("portrait"))


def test_fatal_critic_evidence_rejects_even_above_gate():
    generator = FakeGenerator([("f001", 0.91)])

    class FatalCritic(FakeCritic):
        def critique(self, request, artifact):
            return Critique(
                0.99,
                (CritiqueIssue("identity", "identity mismatch", "fatal", "restore identity"),),
            )

    result = BoundedMediaGenerationController(generator, FatalCritic()).run(
        GenerationRequest("same person", min_score=0.9)
    )
    assert result.status == "rejected"
    assert not result.accepted


def test_duplicate_artifact_stops_stalled_loop():
    generator = FakeGenerator([("dup1", 0.30), ("dup1", 0.35), ("dup2", 0.95)])
    result = BoundedMediaGenerationController(generator, FakeCritic()).run(
        GenerationRequest("scene", max_attempts=3, min_score=0.9)
    )
    assert result.status == "exhausted"
    assert "duplicate artifact" in result.stop_reason
    assert len(result.steps) == 2


def test_request_validation_separates_image_and_video_fields():
    with pytest.raises(ValueError):
        GenerationRequest("image", duration_s=1.0).validate()
    with pytest.raises(ValueError):
        GenerationRequest("video", media_type="video", duration_s=0.0, fps=24).validate()
