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


class RewardModulatedCapabilityGate(SparseCapabilityGate):
    """Adds a tiny FCA-style local value memory to sparse capability selection.

    This does not retrain the planner. It only biases later bids using observed
    capability reward, keeping the adaptation bounded and inspectable.
    """

    def __init__(
        self,
        *,
        budget: float = 1.0,
        max_active: int = 3,
        learning_rate: float = 0.15,
        decay: float = 0.995,
        preference_limit: float = 2.0,
    ) -> None:
        super().__init__(budget=budget, max_active=max_active)
        if not 0.0 < learning_rate <= 1.0:
            raise ValueError("learning_rate must be in (0,1]")
        if not 0.0 < decay <= 1.0:
            raise ValueError("decay must be in (0,1]")
        if preference_limit <= 0.0:
            raise ValueError("preference_limit must be positive")
        self.learning_rate = float(learning_rate)
        self.decay = float(decay)
        self.preference_limit = float(preference_limit)
        self.preferences: dict[str, float] = {}

    def observe(self, capability: str, reward: float) -> float:
        name = str(capability).strip()
        if not name:
            raise ValueError("capability is required")
        old = self.preferences.get(name, 0.0) * self.decay
        prediction_error = float(reward) - old
        updated = old + self.learning_rate * prediction_error
        updated = max(-self.preference_limit, min(self.preference_limit, updated))
        self.preferences[name] = updated
        return prediction_error

    def select(
        self,
        bids: Iterable[CapabilityBid],
        available: Iterable[str],
    ) -> tuple[str, ...]:
        adjusted = [
            CapabilityBid(
                name=bid.name,
                relevance=bid.relevance,
                expected_value=bid.expected_value + self.preferences.get(bid.name, 0.0),
                information_gain=bid.information_gain,
                cost=bid.cost,
            )
            for bid in bids
        ]
        return super().select(adjusted, available)

    def snapshot(self) -> dict[str, float]:
        return dict(self.preferences)

    def restore(self, snapshot: dict[str, float]) -> None:
        if not isinstance(snapshot, dict):
            raise ValueError("preference snapshot must be an object")
        restored: dict[str, float] = {}
        for name, value in snapshot.items():
            key = str(name).strip()
            val = float(value)
            if not key or abs(val) > self.preference_limit:
                raise ValueError("invalid preference snapshot")
            restored[key] = val
        self.preferences = restored
