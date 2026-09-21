from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from fap_media_generation import Critique, GenerationRequest, MediaArtifact
from fap_observed_media import CompositeCritic, ObserverBinding, ObservedMediaGenerator


@dataclass(frozen=True)
class CandidateLane:
    backend_id: str
    generator: Any
    observers: tuple[ObserverBinding, ...]

    def validate(self) -> None:
        if not isinstance(self.backend_id, str) or not self.backend_id.strip():
            raise ValueError("backend_id is required")
        if not callable(getattr(self.generator, "generate", None)):
            raise TypeError("lane generator must provide generate()")
        if not self.observers:
            raise ValueError("lane requires at least one observer")


@dataclass(frozen=True)
class PortfolioCandidate:
    backend_id: str
    artifact: MediaArtifact
    critique: Critique
    prompt: str
    round_index: int


@dataclass(frozen=True)
class PortfolioRound:
    index: int
    prompt: str
    candidates: tuple[PortfolioCandidate, ...]
    lane_errors: tuple[tuple[str, str], ...]
    winner_backend_id: str | None


@dataclass(frozen=True)
class PortfolioGenerationResult:
    status: str
    best_candidate: PortfolioCandidate | None
    rounds: tuple[PortfolioRound, ...]
    stop_reason: str

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


class PortfolioMediaGenerationController:
    """Compete multiple observed generation backends under one critic stack.

    Each backend must pass through its own ObservedMediaGenerator, so candidates
    are compared only after evidence has been attached to the exact artifact.
    """

    def __init__(self, lanes: Sequence[CandidateLane], critics: Sequence[Any]):
        if not lanes:
            raise ValueError("at least one candidate lane is required")
        if len(lanes) > 8:
            raise ValueError("too many candidate lanes")
        seen: set[str] = set()
        normalized = []
        for lane in lanes:
            lane.validate()
            if lane.backend_id in seen:
                raise ValueError("duplicate backend_id")
            seen.add(lane.backend_id)
            normalized.append(
                (
                    lane.backend_id,
                    ObservedMediaGenerator(lane.generator, lane.observers),
                )
            )
        self.lanes = tuple(normalized)
        self.critic = CompositeCritic(critics)

    def run(self, request: GenerationRequest) -> PortfolioGenerationResult:
        request.validate()
        prompt = request.prompt.strip()
        rounds: list[PortfolioRound] = []
        best: PortfolioCandidate | None = None
        previous_by_lane: dict[str, MediaArtifact] = {}
        critique_by_lane: dict[str, Critique] = {}
        seen_by_lane: dict[str, set[str]] = {
            backend_id: set() for backend_id, _ in self.lanes
        }

        for round_index in range(1, request.max_attempts + 1):
            candidates: list[PortfolioCandidate] = []
            errors: list[tuple[str, str]] = []

            for backend_id, generator in self.lanes:
                try:
                    artifact = generator.generate(
                        request,
                        prompt=prompt,
                        previous=previous_by_lane.get(backend_id),
                        critique=critique_by_lane.get(backend_id),
                    )
                    artifact.validate()
                    if artifact.media_type != request.media_type:
                        raise ValueError("wrong media type")
                    if artifact.digest in seen_by_lane[backend_id]:
                        raise ValueError("duplicate artifact; lane stalled")
                    seen_by_lane[backend_id].add(artifact.digest)

                    critique = self.critic.critique(request, artifact)
                    critique.validate()
                    candidate = PortfolioCandidate(
                        backend_id,
                        artifact,
                        critique,
                        prompt,
                        round_index,
                    )
                    candidates.append(candidate)
                    previous_by_lane[backend_id] = artifact
                    critique_by_lane[backend_id] = critique
                except Exception as exc:
                    errors.append((backend_id, f"{type(exc).__name__}: {exc}"))

            if not candidates:
                rounds.append(
                    PortfolioRound(
                        round_index,
                        prompt,
                        (),
                        tuple(errors),
                        None,
                    )
                )
                return PortfolioGenerationResult(
                    "rejected",
                    best,
                    tuple(rounds),
                    "all candidate lanes failed closed",
                )

            winner = max(
                candidates,
                key=lambda c: (
                    0 if c.critique.has_fatal else 1,
                    float(c.critique.score),
                    c.backend_id,
                ),
            )

            if best is None or self._better(winner, best):
                best = winner

            rounds.append(
                PortfolioRound(
                    round_index,
                    prompt,
                    tuple(candidates),
                    tuple(errors),
                    winner.backend_id,
                )
            )

            acceptable = [
                c for c in candidates
                if not c.critique.has_fatal and c.critique.score >= request.min_score
            ]
            if acceptable:
                accepted = max(
                    acceptable,
                    key=lambda c: (float(c.critique.score), c.backend_id),
                )
                return PortfolioGenerationResult(
                    "accepted",
                    accepted,
                    tuple(rounds),
                    "portfolio quality gate satisfied",
                )

            if best is None or best.critique.has_fatal:
                return PortfolioGenerationResult(
                    "rejected",
                    best,
                    tuple(rounds),
                    "no non-fatal candidate available for repair",
                )

            prompt = self._repair_prompt(request, best.critique)

        return PortfolioGenerationResult(
            "exhausted",
            best,
            tuple(rounds),
            "portfolio attempt budget exhausted",
        )

    @staticmethod
    def _better(a: PortfolioCandidate, b: PortfolioCandidate) -> bool:
        if a.critique.has_fatal != b.critique.has_fatal:
            return not a.critique.has_fatal
        if a.critique.score != b.critique.score:
            return a.critique.score > b.critique.score
        return a.backend_id < b.backend_id

    @staticmethod
    def _repair_prompt(request: GenerationRequest, critique: Critique) -> str:
        hints = []
        for issue in critique.issues:
            hint = issue.repair_hint.strip() or issue.detail.strip()
            if hint:
                hints.append(f"[{issue.code}] {hint}")
        parts = [request.prompt.strip()]
        if request.constraints:
            parts.append("Hard constraints: " + " | ".join(request.constraints))
        if hints:
            parts.append(
                "Repair verified defects from the current best candidate: "
                + " | ".join(hints[:12])
            )
        return "\n".join(parts)
