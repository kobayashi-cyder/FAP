from __future__ import annotations

import pytest

from fap_adaptive_fast_path import AdaptiveFastPathController
from fap_media_generation import Critique, CritiqueIssue, GenerationRequest, MediaArtifact
from fap_media_portfolio import CandidateLane
from fap_observed_media import ObservationEnvelope, ObserverBinding


class SequenceGenerator:
    def __init__(self, backend_id, scores):
        self.backend_id = backend_id
        self.scores = list(scores)
        self.calls = 0

    def generate(self, request, *, prompt, previous, critique):
        self.calls += 1
        score = self.scores[min(self.calls - 1, len(self.scores) - 1)]
        return MediaArtifact(
            request.media_type,
            f"{self.backend_id}-digest-{self.calls:03d}",
            "image/png" if request.media_type == "image" else "video/mp4",
            metadata={"score": score},
        )


class Observer:
    def observe(self, request, artifact):
        return ObservationEnvelope(
            artifact.digest,
            {"seen": artifact.digest},
            observer_id="observer.v1",
            evidence_kind="quality",
        )


class Critic:
    def critique(self, request, artifact):
        score = float(artifact.metadata["score"])
        issues = ()
        if score < request.min_score:
            issues = (
                CritiqueIssue(
                    "quality",
                    "below gate",
                    "medium",
                    "improve fidelity",
                ),
            )
        return Critique(score, issues, evidence={"digest": artifact.digest})


def lane(name, scores):
    return CandidateLane(
        name,
        SequenceGenerator(name, scores),
        (ObserverBinding("quality_evidence", Observer()),),
    )


def request(**kwargs):
    return GenerationRequest(
        "beagle portrait",
        max_attempts=kwargs.get("max_attempts", 3),
        min_score=kwargs.get("min_score", 0.9),
    )


def test_fast_path_accepts_after_one_generator_call():
    lanes = [lane("a", [0.95]), lane("b", [0.99]), lane("c", [0.98])]
    controller = AdaptiveFastPathController(lanes, [Critic()], initial_width=1)
    result = controller.run(request())
    assert result.accepted
    assert result.generator_calls == 1
    assert result.rounds[0].expanded is False


def test_fast_path_expands_only_when_first_lane_misses_gate():
    lanes = [lane("a", [0.70]), lane("b", [0.94]), lane("c", [0.80])]
    controller = AdaptiveFastPathController(lanes, [Critic()], initial_width=1)
    result = controller.run(request())
    assert result.accepted
    assert result.generator_calls == 3
    assert result.rounds[0].expanded is True
    assert result.best_candidate.backend_id == "b"


def test_profile_learning_moves_successful_lane_to_front():
    a = lane("a", [0.60, 0.95])
    b = lane("b", [0.94, 0.94])
    controller = AdaptiveFastPathController([a, b], [Critic()], initial_width=1)
    first = controller.run(request())
    assert first.accepted
    assert first.generator_calls == 2
    second = controller.run(request())
    assert second.accepted
    assert second.generator_calls == 1
    assert second.best_candidate.backend_id == "b"


def test_repair_round_starts_narrow_again():
    a = lane("a", [0.82, 0.93])
    b = lane("b", [0.80, 0.85])
    controller = AdaptiveFastPathController([a, b], [Critic()], initial_width=1, repair_width=1)
    result = controller.run(request(max_attempts=2))
    assert result.accepted
    assert len(result.rounds) == 2
    assert result.generator_calls == 3
    assert result.rounds[0].expanded is True
    assert result.rounds[1].expanded is False


def test_bad_first_lane_does_not_block_portfolio():
    a = lane("a", [0.10])
    b = lane("b", [0.92])
    controller = AdaptiveFastPathController([a, b], [Critic()], initial_width=1)
    result = controller.run(request())
    assert result.accepted
    assert result.best_candidate.backend_id == "b"


def test_video_uses_same_fast_path():
    req = GenerationRequest(
        "dog running",
        media_type="video",
        duration_s=3.0,
        fps=24,
        max_attempts=2,
        min_score=0.9,
    )
    controller = AdaptiveFastPathController(
        [lane("v1", [0.93]), lane("v2", [0.99])],
        [Critic()],
        initial_width=1,
    )
    result = controller.run(req)
    assert result.accepted
    assert result.generator_calls == 1
    assert result.best_candidate.artifact.mime_type == "video/mp4"


def test_duplicate_backend_id_rejected():
    with pytest.raises(ValueError):
        AdaptiveFastPathController(
            [lane("same", [0.9]), lane("same", [0.9])],
            [Critic()],
        )
