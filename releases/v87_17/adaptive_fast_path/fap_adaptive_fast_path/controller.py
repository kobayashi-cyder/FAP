from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from fap_media_generation import Critique, GenerationRequest, MediaArtifact
from fap_media_portfolio import CandidateLane, PortfolioCandidate
from fap_observed_media import CompositeCritic, ObservedMediaGenerator


@dataclass
class LaneProfile:
    backend_id: str
    attempts: int = 0
    accepted: int = 0
    failures: int = 0
    score_ema: float = 0.50

    def update_success(self, score: float, *, accepted: bool, alpha: float = 0.35) -> None:
        self.attempts += 1
        self.score_ema = alpha * float(score) + (1.0 - alpha) * self.score_ema
        if accepted:
            self.accepted += 1

    def update_failure(self) -> None:
        self.attempts += 1
        self.failures += 1

    @property
    def reliability(self) -> float:
        if self.attempts == 0:
            return 0.50
        return (self.accepted + 1.0) / (self.attempts + 2.0)

    @property
    def priority(self) -> float:
        failure_penalty = self.failures / max(1, self.attempts)
        return 0.65 * self.score_ema + 0.35 * self.reliability - 0.20 * failure_penalty


@dataclass(frozen=True)
class FastPathRound:
    index: int
    prompt: str
    attempted_backends: tuple[str, ...]
    candidates: tuple[PortfolioCandidate, ...]
    lane_errors: tuple[tuple[str, str], ...]
    expanded: bool


@dataclass(frozen=True)
class AdaptiveFastPathResult:
    status: str
    best_candidate: PortfolioCandidate | None
    rounds: tuple[FastPathRound, ...]
    generator_calls: int
    stop_reason: str

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


class AdaptiveFastPathController:
    """Adaptive quality-preserving media routing.

    Fast path:
      1. Try the historically strongest observed lane first.
      2. If it clears the quality gate by itself, accept immediately.
      3. Only expand to additional lanes when the first lane is insufficient.
      4. Repair from the best verified candidate and retry with a narrow lane set
         before re-expanding.

    This reduces generator/observer transitions without weakening the critic gate.
    """

    def __init__(
        self,
        lanes: Sequence[CandidateLane],
        critics: Sequence[Any],
        *,
        initial_width: int = 1,
        repair_width: int = 1,
    ):
        if not lanes:
            raise ValueError("at least one lane is required")
        if len(lanes) > 8:
            raise ValueError("too many lanes")
        if initial_width < 1 or repair_width < 1:
            raise ValueError("lane widths must be positive")

        seen: set[str] = set()
        wrapped = {}
        profiles = {}
        for lane in lanes:
            lane.validate()
            if lane.backend_id in seen:
                raise ValueError("duplicate backend_id")
            seen.add(lane.backend_id)
            wrapped[lane.backend_id] = ObservedMediaGenerator(lane.generator, lane.observers)
            profiles[lane.backend_id] = LaneProfile(lane.backend_id)

        self._wrapped = wrapped
        self.profiles = profiles
        self.critic = CompositeCritic(critics)
        self.initial_width = min(initial_width, len(wrapped))
        self.repair_width = min(repair_width, len(wrapped))

    def run(self, request: GenerationRequest) -> AdaptiveFastPathResult:
        request.validate()
        prompt = request.prompt.strip()
        rounds: list[FastPathRound] = []
        best: PortfolioCandidate | None = None
        previous_by_lane: dict[str, MediaArtifact] = {}
        critique_by_lane: dict[str, Critique] = {}
        seen_by_lane: dict[str, set[str]] = {k: set() for k in self._wrapped}
        generator_calls = 0

        for round_index in range(1, request.max_attempts + 1):
            ordered = self._ordered_backends()
            width = self.initial_width if round_index == 1 else self.repair_width
            narrow = ordered[:width]

            candidates, errors, calls = self._attempt_lanes(
                narrow,
                request,
                prompt,
                round_index,
                previous_by_lane,
                critique_by_lane,
                seen_by_lane,
            )
            generator_calls += calls

            accepted = self._best_acceptable(candidates, request.min_score)
            if accepted is not None:
                if best is None or self._better(accepted, best):
                    best = accepted
                rounds.append(
                    FastPathRound(
                        round_index,
                        prompt,
                        tuple(narrow),
                        tuple(candidates),
                        tuple(errors),
                        False,
                    )
                )
                return AdaptiveFastPathResult(
                    "accepted",
                    best,
                    tuple(rounds),
                    generator_calls,
                    "fast-path quality gate satisfied",
                )

            expanded = False
            remaining = [backend_id for backend_id in ordered if backend_id not in narrow]
            if remaining:
                expanded = True
                extra_candidates, extra_errors, calls = self._attempt_lanes(
                    remaining,
                    request,
                    prompt,
                    round_index,
                    previous_by_lane,
                    critique_by_lane,
                    seen_by_lane,
                )
                generator_calls += calls
                candidates.extend(extra_candidates)
                errors.extend(extra_errors)

            winner = self._best_nonfatal(candidates)
            if winner is not None and (best is None or self._better(winner, best)):
                best = winner

            rounds.append(
                FastPathRound(
                    round_index,
                    prompt,
                    tuple(narrow + remaining if expanded else narrow),
                    tuple(candidates),
                    tuple(errors),
                    expanded,
                )
            )

            accepted = self._best_acceptable(candidates, request.min_score)
            if accepted is not None:
                if best is None or self._better(accepted, best):
                    best = accepted
                return AdaptiveFastPathResult(
                    "accepted",
                    best,
                    tuple(rounds),
                    generator_calls,
                    "expanded quality gate satisfied",
                )

            if best is None or best.critique.has_fatal:
                return AdaptiveFastPathResult(
                    "rejected",
                    best,
                    tuple(rounds),
                    generator_calls,
                    "no non-fatal candidate available",
                )

            prompt = self._repair_prompt(request, best.critique)

        return AdaptiveFastPathResult(
            "exhausted",
            best,
            tuple(rounds),
            generator_calls,
            "attempt budget exhausted",
        )

    def _attempt_lanes(
        self,
        backend_ids,
        request,
        prompt,
        round_index,
        previous_by_lane,
        critique_by_lane,
        seen_by_lane,
    ):
        candidates: list[PortfolioCandidate] = []
        errors: list[tuple[str, str]] = []
        calls = 0
        for backend_id in backend_ids:
            generator = self._wrapped[backend_id]
            calls += 1
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
                self.profiles[backend_id].update_success(
                    critique.score,
                    accepted=(not critique.has_fatal and critique.score >= request.min_score),
                )
            except Exception as exc:
                self.profiles[backend_id].update_failure()
                errors.append((backend_id, f"{type(exc).__name__}: {exc}"))
        return candidates, errors, calls

    def _ordered_backends(self) -> list[str]:
        return sorted(
            self._wrapped,
            key=lambda backend_id: (
                -self.profiles[backend_id].priority,
                backend_id,
            ),
        )

    @staticmethod
    def _best_acceptable(candidates, min_score):
        acceptable = [
            c for c in candidates
            if not c.critique.has_fatal and c.critique.score >= min_score
        ]
        if not acceptable:
            return None
        return max(acceptable, key=lambda c: (float(c.critique.score), c.backend_id))

    @staticmethod
    def _best_nonfatal(candidates):
        viable = [c for c in candidates if not c.critique.has_fatal]
        if not viable:
            return None
        return max(viable, key=lambda c: (float(c.critique.score), c.backend_id))

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
            parts.append("Repair verified defects: " + " | ".join(hints[:12]))
        return "\n".join(parts)
