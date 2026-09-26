from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


@dataclass(frozen=True)
class Signal:
    kind: str
    weight: float = 0.5
    count: int = 1


@dataclass(frozen=True)
class Budget:
    routes: int
    steps: int
    verify: int
    retries: int


def _clip(value: float, *, invalid: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return invalid
    if not isfinite(numeric):
        return invalid
    return max(0.0, min(1.0, numeric))


def _bounded_count(value: object) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return 1
    return min(max(numeric, 1), 8)


def adaptive_budget(
    signals: Iterable[Signal] | None = (),
    *,
    uncertainty: float = 0.0,
    disagreement: bool = False,
) -> Budget:
    """Public, answer-independent adaptive budget for FAP 1.0.0-r001.

    Boundary policy:
    - malformed signal entries are ignored rather than crashing the public gate;
    - non-finite/invalid weights contribute zero difficulty;
    - invalid counts fall back to one bounded observation;
    - invalid uncertainty contributes zero rather than being interpreted as
      maximum confidence pressure.
    """
    difficulty = 0.0
    for signal in signals or ():
        if not isinstance(signal, Signal):
            continue
        difficulty += (
            _clip(signal.weight)
            * _bounded_count(signal.count)
            / 8.0
        )
    pressure = _clip(
        0.55 * _clip(difficulty)
        + 0.35 * _clip(uncertainty)
        + 0.10 * int(bool(disagreement))
    )

    return Budget(
        routes=min(8, 1 + int(pressure >= 0.20) + int(pressure >= 0.50) + int(pressure >= 0.80)),
        steps=min(96, 8 + round(72 * pressure)),
        verify=min(6, 1 + int(pressure >= 0.25) + int(pressure >= 0.55) + int(pressure >= 0.80)),
        retries=min(4, int(pressure >= 0.40) + int(pressure >= 0.75)),
    )


def needs_extra_path(
    *,
    confidence: float,
    disagreement: bool = False,
    counterexample: bool = False,
) -> bool:
    # Invalid/non-finite confidence must fail toward more checking, not toward
    # trusting the primary path.
    safe_confidence = _clip(confidence, invalid=0.0)
    return (
        safe_confidence < 0.70
        or bool(disagreement)
        or bool(counterexample)
    )
