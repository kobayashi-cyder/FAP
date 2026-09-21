from __future__ import annotations

from dataclasses import dataclass

import pytest

from fap_media_generation import Critique, CritiqueIssue, GenerationRequest, MediaArtifact
from fap_media_portfolio import CandidateLane, PortfolioMediaGenerationController
from fap_observed_media import ObservationEnvelope, ObserverBinding


class SequenceGenerator:
    def __init__(self, backend_id, scores, *, fail_on=None):
        self.backend_id = backend_id
        self.scores = list(scores)
        self.calls = 0
        self.fail_on = fail_on

    def generate(self, request, *, prompt, previous, critique):
        self.calls += 1
        if self.fail_on == self.calls:
            raise RuntimeError("backend failure")
        index = min(self.calls - 1, len(self.scores) - 1)
        score = self.scores[index]
        return MediaArtifact(
            request.media_type,
            f"{self.backend_id}-{self.calls}",
            "video/mp4" if request.media_type == "video" else "image/png",
            metadata={"raw_score": score},
        )


class PassObserver:
    def __init__(self, observer_id):
        self.observer_id = observer_id

    def observe(self, request, artifact):
        return ObservationEnvelope(
            artifact.digest,
            {"observed": artifact.digest},
            observer_id=self.observer_id,
            evidence_kind="quality",
        )


class MetadataCritic:
    def critique(self, request, artifact):
        score = float(artifact.metadata["raw_score"])
        issues = ()
        if score < request.min_score:
            issues = (
                CritiqueIssue(
                    "quality",
                    "candidate below quality gate",
                    "medium",
                    "improve composition and fidelity",
                ),
            )
        return Critique(score, issues, evidence={"digest": artifact.digest})


def lane(name, scores, *, fail_on=None):
    return CandidateLane(
        name,
        SequenceGenerator(name, scores, fail_on=fail_on),
        (ObserverBinding("quality_evidence", PassObserver(f"obs-{name}")),),
    )


def image_request(**kwargs):
    return GenerationRequest("beagle portrait", max_attempts=kwargs.get("max_attempts", 3), min_score=kwargs.get("min_score", 0.9))


def test_portfolio_selects_best_backend_in_same_round():
    controller = PortfolioMediaGenerationController(
        [lane("a", [0.70]), lane("b", [0.94]), lane("c", [0.82])],
        [MetadataCritic()],
    )
    result = controller.run(image_request())
    assert result.accepted
    assert result.best_candidate.backend_id == "b"
    assert len(result.rounds) == 1
    assert len(result.rounds[0].candidates) == 3


def test_portfolio_repairs_and_recompetes():
    controller = PortfolioMediaGenerationController(
        [lane("a", [0.60, 0.91]), lane("b", [0.75, 0.88])],
        [MetadataCritic()],
    )
    result = controller.run(image_request(max_attempts=3))
    assert result.accepted
    assert result.best_candidate.backend_id == "a"
    assert len(result.rounds) == 2
    assert "Repair verified defects" in result.rounds[1].prompt


def test_one_lane_failure_does_not_hide_good_candidate():
    controller = PortfolioMediaGenerationController(
        [lane("broken", [0.99], fail_on=1), lane("good", [0.93])],
        [MetadataCritic()],
    )
    result = controller.run(image_request())
    assert result.accepted
    assert result.best_candidate.backend_id == "good"
    assert result.rounds[0].lane_errors[0][0] == "broken"


def test_all_lanes_failure_rejects():
    controller = PortfolioMediaGenerationController(
        [lane("a", [0.9], fail_on=1), lane("b", [0.9], fail_on=1)],
        [MetadataCritic()],
    )
    result = controller.run(image_request())
    assert result.status == "rejected"
    assert result.best_candidate is None


def test_best_candidate_survives_later_regression():
    controller = PortfolioMediaGenerationController(
        [lane("a", [0.85, 0.50]), lane("b", [0.80, 0.70])],
        [MetadataCritic()],
    )
    result = controller.run(image_request(max_attempts=2, min_score=0.95))
    assert result.status == "exhausted"
    assert result.best_candidate.backend_id == "a"
    assert result.best_candidate.critique.score == 0.85


def test_duplicate_backend_id_is_rejected():
    with pytest.raises(ValueError):
        PortfolioMediaGenerationController(
            [lane("same", [0.9]), lane("same", [0.8])],
            [MetadataCritic()],
        )


def test_video_portfolio_uses_same_observed_competition():
    request = GenerationRequest(
        "dog running through surf",
        media_type="video",
        duration_s=4.0,
        fps=24,
        max_attempts=2,
        min_score=0.9,
    )
    controller = PortfolioMediaGenerationController(
        [lane("v1", [0.89, 0.93]), lane("v2", [0.91])],
        [MetadataCritic()],
    )
    result = controller.run(request)
    assert result.accepted
    assert result.best_candidate.backend_id == "v2"
    assert result.best_candidate.artifact.mime_type == "video/mp4"


def test_lane_candidate_contains_digest_bound_observation_manifest():
    controller = PortfolioMediaGenerationController(
        [lane("a", [0.95])],
        [MetadataCritic()],
    )
    result = controller.run(image_request())
    candidate = result.best_candidate
    manifest = candidate.artifact.metadata["observation_manifest"]["quality_evidence"]
    assert manifest["artifact_digest"] == candidate.artifact.digest
