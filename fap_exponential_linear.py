from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, exp, isfinite, log1p
import re


@dataclass(frozen=True)
class ExponentialLinearPolicy:
    """Bounded exponential-to-linear capacity scaling.

    For normalized demand x in [0, 1]:

        exp(alpha*x)                              if x <= knee
        exp(alpha*knee) * (1 + alpha*(x-knee))  otherwise

    The second segment is the tangent line of the exponential at the knee, so
    value and first derivative are continuous. max_scale is a hard bound.
    """

    alpha: float = 2.6
    knee: float = 0.55
    max_scale: float = 12.0

    def __post_init__(self) -> None:
        alpha = float(self.alpha)
        knee = float(self.knee)
        max_scale = float(self.max_scale)
        if not isfinite(alpha) or alpha <= 0.0:
            raise ValueError("alpha must be finite and positive")
        if not isfinite(knee) or not 0.0 < knee < 1.0:
            raise ValueError("knee must be in (0, 1)")
        if not isfinite(max_scale) or max_scale < 1.0:
            raise ValueError("max_scale must be finite and >= 1")

    def scale(self, demand: float) -> float:
        x = float(demand)
        if not isfinite(x):
            raise ValueError("demand must be finite")
        x = min(1.0, max(0.0, x))
        if x <= self.knee:
            raw = exp(self.alpha * x)
        else:
            at_knee = exp(self.alpha * self.knee)
            raw = at_knee * (1.0 + self.alpha * (x - self.knee))
        return min(float(self.max_scale), max(1.0, raw))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InteractionDemand:
    value: float
    char_component: float
    token_component: float
    structure_component: float
    diversity_component: float
    history_component: float
    hint_component: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InteractionBudget:
    demand: float
    scale: float
    route_candidates: int
    context_chars: int
    source_bytes: int
    reasoning_steps: int
    repair_rounds: int
    output_chars: int

    def to_dict(self) -> dict:
        return asdict(self)


_TOKEN_RE = re.compile(r"[\w\u3040-\u30ff\u3400-\u9fff]+", re.UNICODE)


def estimate_interaction_demand(
    text: str,
    *,
    history_turns: int = 0,
    pressure_hint: float = 0.0,
    max_chars: int = 100_000,
) -> InteractionDemand:
    """Estimate generic demand from structure, not subject-specific branches."""
    value = str(text or "")
    if max_chars < 256:
        raise ValueError("max_chars must be >= 256")
    if len(value) > max_chars:
        value = value[:max_chars]

    try:
        turns = int(history_turns)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("history_turns must be an integer") from exc
    if turns < 0:
        raise ValueError("history_turns must be non-negative")

    hint = float(pressure_hint)
    if not isfinite(hint):
        raise ValueError("pressure_hint must be finite")
    hint = min(1.0, max(0.0, hint))

    stripped = value.strip()
    tokens = _TOKEN_RE.findall(stripped.casefold())
    unique = len(set(tokens))
    token_count = len(tokens)

    char_component = (
        min(1.0, log1p(len(stripped)) / log1p(max_chars))
        if stripped
        else 0.0
    )
    token_component = min(1.0, token_count / 512.0)
    lines = 0 if not stripped else stripped.count("\n") + 1
    structure_component = min(1.0, lines / 32.0)
    diversity_component = (
        min(1.0, unique / max(1, token_count))
        if token_count
        else 0.0
    )
    history_component = min(1.0, turns / 32.0)

    demand = (
        0.42 * char_component
        + 0.18 * token_component
        + 0.12 * structure_component
        + 0.12 * diversity_component
        + 0.11 * history_component
        + 0.05 * hint
    )
    demand = min(1.0, max(0.0, demand))
    return InteractionDemand(
        value=demand,
        char_component=char_component,
        token_component=token_component,
        structure_component=structure_component,
        diversity_component=diversity_component,
        history_component=history_component,
        hint_component=hint,
    )


def budget_for_demand(
    demand: InteractionDemand | float,
    *,
    policy: ExponentialLinearPolicy | None = None,
) -> InteractionBudget:
    policy = policy or ExponentialLinearPolicy()
    value = demand.value if isinstance(demand, InteractionDemand) else float(demand)
    scale = policy.scale(value)

    return InteractionBudget(
        demand=min(1.0, max(0.0, float(value))),
        scale=scale,
        route_candidates=min(32, max(1, ceil(2.0 * scale))),
        context_chars=min(250_000, max(4_000, ceil(8_000 * scale))),
        source_bytes=min(1_000_000, max(30_000, ceil(60_000 * scale))),
        reasoning_steps=min(96, max(4, ceil(5.0 * scale))),
        repair_rounds=min(4, max(0, ceil(scale / 3.0) - 1)),
        output_chars=min(120_000, max(4_000, ceil(5_000 * scale))),
    )
