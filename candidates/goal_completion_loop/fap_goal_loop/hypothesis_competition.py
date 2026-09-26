from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hypothesis:
    """A candidate explanation/plan claim that is not itself verified evidence."""

    key: str
    confidence: float
    support: int = 0
    contradictions: int = 0
    novelty: float = 0.0
    verification_cost: float = 0.0

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("hypothesis key must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        if self.support < 0 or self.contradictions < 0:
            raise ValueError("counts must be non-negative")
        if self.verification_cost < 0:
            raise ValueError("verification_cost must be non-negative")

    @property
    def score(self) -> float:
        return (
            self.confidence
            + 0.10 * self.support
            + 0.10 * self.novelty
            - 0.20 * self.contradictions
            - 0.05 * self.verification_cost
        )


class BoundedHypothesisCompetition:
    """Ranks competing candidates while keeping verification authoritative.

    This is intentionally a bounded advisory component.  It can prioritize
    candidates for FAP's planner/executor, but it cannot mark a goal complete,
    manufacture evidence, or bypass the critic/verification boundary.
    """

    def __init__(self, max_active: int = 4) -> None:
        if max_active < 1:
            raise ValueError("max_active must be positive")
        self.max_active = max_active

    def select(self, hypotheses: list[Hypothesis]) -> tuple[Hypothesis, ...]:
        # Deduplicate by stable key, retaining only the strongest candidate.
        strongest: dict[str, Hypothesis] = {}
        for hypothesis in hypotheses:
            old = strongest.get(hypothesis.key)
            if old is None or hypothesis.score > old.score:
                strongest[hypothesis.key] = hypothesis
        ranked = sorted(strongest.values(), key=lambda h: (-h.score, h.key))
        return tuple(ranked[: self.max_active])
