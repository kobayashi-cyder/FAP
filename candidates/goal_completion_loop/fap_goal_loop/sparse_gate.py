from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Any


@dataclass(frozen=True)
class CapabilityBid:
    name: str
    relevance: float
    expected_value: float
    information_gain: float
    cost: float

    @property
    def score(self) -> float:
        return self.relevance * (self.expected_value + self.information_gain) - self.cost


class SparseCapabilityGate:
    """FCA-derived sparse activation gate for FAP capabilities."""

    def __init__(self, *, budget: float = 1.0, max_active: int = 3) -> None:
        if budget <= 0.0 or max_active < 1:
            raise ValueError("invalid sparse-gate budget")
        self.budget = float(budget)
        self.max_active = int(max_active)

    def select(
        self,
        bids: Iterable[CapabilityBid],
        available: Iterable[str],
    ) -> tuple[str, ...]:
        allowed = frozenset(str(x) for x in available)
        chosen: list[str] = []
        spent = 0.0
        seen: set[str] = set()
        for bid in sorted(bids, key=lambda b: (b.score, -b.cost, b.name), reverse=True):
            if bid.name in seen or bid.name not in allowed or bid.score <= 0.0:
                continue
            if len(chosen) >= self.max_active:
                break
            if bid.cost < 0.0 or spent + bid.cost > self.budget:
                continue
            chosen.append(bid.name)
            seen.add(bid.name)
            spent += bid.cost
        return tuple(chosen)

    def as_selector(
        self,
        bid_provider: Callable[[Any, Any, frozenset[str]], Iterable[CapabilityBid]],
    ) -> Callable[[Any, Any, frozenset[str]], tuple[str, ...]]:
        def selector(goal: Any, state: Any, available: frozenset[str]) -> tuple[str, ...]:
            return self.select(bid_provider(goal, state, available), available)
        return selector
