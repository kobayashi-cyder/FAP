from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from statistics import median
from typing import Iterable, Mapping, Sequence

from fap_revision_r001 import Budget, Signal, adaptive_budget, needs_extra_path


def _clip(value: float) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError("route values must be finite")
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class Route:
    name: str
    tags: tuple[str, ...] = ()
    relevance: float = 0.5
    evidence: float = 0.5
    cost: float = 0.5
    novelty: float = 0.5

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("route name must be non-empty")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(
            self,
            "tags",
            tuple(dict.fromkeys(tag.strip() for tag in self.tags if tag.strip())),
        )
        object.__setattr__(self, "relevance", _clip(self.relevance))
        object.__setattr__(self, "evidence", _clip(self.evidence))
        object.__setattr__(self, "cost", _clip(self.cost))
        object.__setattr__(self, "novelty", _clip(self.novelty))


@dataclass(frozen=True)
class ScoredRoute:
    name: str
    score: float
    matched_signals: tuple[str, ...]


@dataclass(frozen=True)
class SparsePlan:
    budget: Budget
    active: tuple[str, ...]
    reserve: tuple[str, ...]
    scores: tuple[ScoredRoute, ...]
    edges: tuple[tuple[str, str], ...]
    route_cap: int


@dataclass(frozen=True)
class RouteOutcome:
    name: str
    confidence: float
    verified: bool
    useful: bool = True
    contradiction: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _clip(self.confidence))


@dataclass(frozen=True)
class VerificationDecision:
    status: str
    confidence: float
    disagreement: bool
    verified_routes: int


def _normalized_priors(priors: Mapping[str, float] | None) -> dict[str, float]:
    return {str(name): _clip(value) for name, value in (priors or {}).items()}


def _signal_affinity(
    route: Route,
    signals: Sequence[Signal],
) -> tuple[float, tuple[str, ...]]:
    if not route.tags or not signals:
        return 0.0, ()

    tags = set(route.tags)
    affinity = 0.0
    matched: list[str] = []
    for signal in signals:
        kind = str(signal.kind).strip()
        if kind and kind in tags:
            strength = (
                _clip(signal.weight)
                * min(max(int(signal.count), 1), 8)
                / 8.0
            )
            affinity += strength
            matched.append(kind)
    return min(1.0, affinity), tuple(dict.fromkeys(matched))


def _base_score(route: Route, *, prior: float, affinity: float) -> float:
    # General routing objective only. Answer content never enters the score.
    return (
        0.34 * route.relevance
        + 0.22 * route.evidence
        + 0.18 * prior
        + 0.16 * affinity
        + 0.10 * route.novelty
        - 0.14 * route.cost
    )


def _overlap(a: Route, b: Route) -> float:
    left, right = set(a.tags), set(b.tags)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _diverse_order(
    routes: Sequence[Route],
    raw_scores: Mapping[str, float],
) -> list[Route]:
    remaining = list(routes)
    selected: list[Route] = []

    while remaining:
        def key(route: Route) -> tuple[float, float, str]:
            overlap = max(
                (_overlap(route, chosen) for chosen in selected),
                default=0.0,
            )
            # Keep near-duplicate specialists from occupying every active slot.
            diversified = raw_scores[route.name] - 0.18 * overlap
            return diversified, raw_scores[route.name], route.name

        best = max(remaining, key=key)
        selected.append(best)
        remaining.remove(best)

    return selected


def _dense_edges(active: Sequence[Route]) -> tuple[tuple[str, str], ...]:
    # A tiny clique gives the initial graph cross-check paths without making
    # the whole specialist pool resident.
    return tuple(
        (active[i].name, active[j].name)
        for i in range(len(active))
        for j in range(i + 1, len(active))
    )


def plan_routes(
    routes: Iterable[Route],
    signals: Iterable[Signal] = (),
    *,
    uncertainty: float = 0.0,
    disagreement: bool = False,
    priors: Mapping[str, float] | None = None,
) -> SparsePlan:
    pool = tuple(routes)
    if not pool:
        raise ValueError("at least one route is required")

    names = [route.name for route in pool]
    if len(set(names)) != len(names):
        raise ValueError("route names must be unique")

    signal_list = tuple(signals)
    prior_map = _normalized_priors(priors)
    budget = adaptive_budget(
        signal_list,
        uncertainty=_clip(uncertainty),
        disagreement=disagreement,
    )

    raw_scores: dict[str, float] = {}
    matched: dict[str, tuple[str, ...]] = {}
    for route in pool:
        affinity, route_matches = _signal_affinity(route, signal_list)
        raw_scores[route.name] = _base_score(
            route,
            prior=prior_map.get(route.name, 0.5),
            affinity=affinity,
        )
        matched[route.name] = route_matches

    ordered = _diverse_order(pool, raw_scores)

    # r001 activates one easy-path route. r002 starts with a tiny two-route
    # graph when possible, then raises capacity only with measured pressure.
    route_cap = min(len(pool), max(2, budget.routes + 1))
    initial_width = min(route_cap, 2 + int(budget.routes >= 3))
    active_routes = ordered[:initial_width]
    reserve_routes = ordered[initial_width:]

    scored = tuple(
        ScoredRoute(
            route.name,
            round(raw_scores[route.name], 8),
            matched[route.name],
        )
        for route in ordered
    )

    return SparsePlan(
        budget=budget,
        active=tuple(route.name for route in active_routes),
        reserve=tuple(route.name for route in reserve_routes),
        scores=scored,
        edges=_dense_edges(active_routes),
        route_cap=route_cap,
    )


def verification_decision(
    outcomes: Iterable[RouteOutcome],
) -> VerificationDecision:
    verified = [outcome for outcome in outcomes if outcome.verified]
    if not verified:
        return VerificationDecision("unresolved", 0.0, False, 0)

    positive = [
        outcome
        for outcome in verified
        if outcome.useful and not outcome.contradiction
    ]
    negative = [
        outcome
        for outcome in verified
        if (not outcome.useful) or outcome.contradiction
    ]
    disagreement = bool(positive and negative)
    confidence = median(outcome.confidence for outcome in verified)

    if disagreement:
        status = "disputed"
    elif positive:
        status = "supported"
    else:
        status = "rejected"

    return VerificationDecision(
        status,
        confidence,
        disagreement,
        len(verified),
    )


def expand_plan(
    plan: SparsePlan,
    outcomes: Iterable[RouteOutcome],
    *,
    counterexample: bool = False,
) -> SparsePlan:
    decision = verification_decision(outcomes)
    need_more = needs_extra_path(
        confidence=decision.confidence,
        disagreement=decision.disagreement,
        counterexample=counterexample,
    ) or decision.verified_routes < min(plan.budget.verify, len(plan.active))

    if (
        not need_more
        or len(plan.active) >= plan.route_cap
        or not plan.reserve
    ):
        return plan

    add_count = min(
        plan.route_cap - len(plan.active),
        max(1, int(decision.disagreement) + int(counterexample)),
        len(plan.reserve),
    )
    additions = plan.reserve[:add_count]
    active = plan.active + additions
    edges = tuple(
        (active[i], active[j])
        for i in range(len(active))
        for j in range(i + 1, len(active))
    )

    return replace(
        plan,
        active=active,
        reserve=plan.reserve[add_count:],
        edges=edges,
    )


def update_route_priors(
    priors: Mapping[str, float] | None,
    outcomes: Iterable[RouteOutcome],
    *,
    learning_rate: float = 0.12,
) -> dict[str, float]:
    rate = _clip(learning_rate)
    updated = _normalized_priors(priors)

    for outcome in outcomes:
        # Fail closed: unverified success/failure never teaches the router.
        if not outcome.verified:
            continue

        old = updated.get(outcome.name, 0.5)
        target = (
            outcome.confidence
            if outcome.useful and not outcome.contradiction
            else 0.0
        )
        updated[outcome.name] = _clip(old + rate * (target - old))

    return updated
