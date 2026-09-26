from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from math import isfinite, log, sqrt
from typing import Iterable, Mapping


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


def _safe_unit(value: object, *, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(number):
        return default
    return _clamp(number, 0.0, 1.0)


def _norm_label(value: object) -> str:
    raw = str(value or "").strip().casefold()
    out = []
    for char in raw:
        if char.isalnum() or char in "_.:-":
            out.append(char)
        elif char.isspace() or char in "/":
            out.append("_")
    return "".join(out).strip("_:")[:96]


def _stable_unit(seed: str, *parts: str) -> float:
    raw = "\x1f".join((seed, *parts)).encode("utf-8")
    digest = sha256(raw).digest()
    integer = int.from_bytes(digest[:8], "big", signed=False)
    return integer / float((1 << 64) - 1)


@dataclass(frozen=True)
class DynamicSparseConfig:
    initial_density: float = 0.38
    sparse_floor: float = 0.16
    sparse_target: float = 0.22
    min_initial_degree: int = 2
    warmup_steps: int = 24
    propagation_hops: int = 2
    propagation_gain: float = 0.30
    exploration_strength: float = 0.20
    exploration_floor: float = 0.06
    cost_penalty: float = 0.10
    success_lr: float = 0.16
    failure_lr: float = 0.12
    edge_decay: float = 0.992
    node_decay: float = 0.996
    prune_threshold: float = 0.18
    reactivate_threshold: float = 0.42
    reactivation_budget: int = 4
    max_selected_routes: int = 8
    max_path_length: int = 4
    path_beam_width: int = 8
    path_alternatives: int = 3

    def __post_init__(self) -> None:
        for name in (
            "initial_density",
            "sparse_floor",
            "sparse_target",
            "propagation_gain",
            "exploration_strength",
            "exploration_floor",
            "cost_penalty",
            "success_lr",
            "failure_lr",
            "edge_decay",
            "node_decay",
            "prune_threshold",
            "reactivate_threshold",
        ):
            value = float(getattr(self, name))
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0.05 <= self.sparse_floor <= self.sparse_target <= self.initial_density <= 0.80:
            raise ValueError("density values must satisfy floor <= target <= initial <= 0.80")
        if not 0.0 <= self.propagation_gain <= 1.0:
            raise ValueError("propagation_gain must be in [0, 1]")
        if not 0.0 <= self.exploration_strength <= 1.0:
            raise ValueError("exploration_strength must be in [0, 1]")
        if not 0.0 <= self.exploration_floor <= 0.5:
            raise ValueError("exploration_floor must be in [0, 0.5]")
        if not 0.0 <= self.cost_penalty <= 1.0:
            raise ValueError("cost_penalty must be in [0, 1]")
        if not 0.0 <= self.success_lr <= 1.0:
            raise ValueError("success_lr must be in [0, 1]")
        if not 0.0 <= self.failure_lr <= 1.0:
            raise ValueError("failure_lr must be in [0, 1]")
        if not 0.0 <= self.edge_decay <= 1.0:
            raise ValueError("edge_decay must be in [0, 1]")
        if not 0.0 <= self.node_decay <= 1.0:
            raise ValueError("node_decay must be in [0, 1]")
        if not 0.05 <= self.prune_threshold <= 0.95:
            raise ValueError("prune_threshold must be in [0.05, 0.95]")
        if not 0.0 <= self.reactivate_threshold <= 1.0:
            raise ValueError("reactivate_threshold must be in [0, 1]")
        if not 1 <= int(self.min_initial_degree) <= 32:
            raise ValueError("min_initial_degree must be in [1, 32]")
        if not 0 <= int(self.warmup_steps) <= 10_000:
            raise ValueError("warmup_steps must be in [0, 10000]")
        if not 1 <= int(self.propagation_hops) <= 4:
            raise ValueError("propagation_hops must be in [1, 4]")
        if not 1 <= int(self.reactivation_budget) <= 64:
            raise ValueError("reactivation_budget must be in [1, 64]")
        if not 1 <= int(self.max_selected_routes) <= 64:
            raise ValueError("max_selected_routes must be in [1, 64]")
        if not 1 <= int(self.max_path_length) <= 8:
            raise ValueError("max_path_length must be in [1, 8]")
        if not 1 <= int(self.path_beam_width) <= 64:
            raise ValueError("path_beam_width must be in [1, 64]")
        if not 1 <= int(self.path_alternatives) <= 16:
            raise ValueError("path_alternatives must be in [1, 16]")


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    capabilities: tuple[str, ...] = ()
    task_families: tuple[str, ...] = ()
    task_forms: tuple[str, ...] = ()
    failure_specialties: tuple[str, ...] = ()
    prior_quality: float = 0.55
    cost: float = 1.0

    def __post_init__(self) -> None:
        route_id = _norm_label(self.route_id)
        if not route_id or route_id != self.route_id:
            raise ValueError("route_id must already be normalized and non-empty")
        for field_name in (
            "capabilities",
            "task_families",
            "task_forms",
            "failure_specialties",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise TypeError(f"{field_name} must be a tuple")
            normalized = tuple(
                dict.fromkeys(
                    label
                    for label in (_norm_label(value) for value in values)
                    if label
                )
            )
            if values != normalized:
                raise ValueError(
                    f"{field_name} must contain unique normalized labels"
                )
            if len(values) > 64:
                raise ValueError(f"{field_name} exceeds 64 labels")
        if not isfinite(float(self.cost)) or float(self.cost) <= 0.0:
            raise ValueError("cost must be finite and positive")
        if not 0.0 <= float(self.prior_quality) <= 1.0:
            raise ValueError("prior_quality must be in [0, 1]")


@dataclass(frozen=True)
class RoutingContext:
    task_family: str = ""
    task_form: str = ""
    required_capabilities: tuple[str, ...] = ()
    failure_classes: tuple[str, ...] = ()
    uncertainty: float = 0.0
    novelty: float = 0.0
    verifier_disagreement: float = 0.0
    available_routes: tuple[str, ...] = ()
    route_hints: tuple[tuple[str, float], ...] = ()

    def normalized(self) -> "RoutingContext":
        return RoutingContext(
            task_family=_norm_label(self.task_family),
            task_form=_norm_label(self.task_form),
            required_capabilities=tuple(
                dict.fromkeys(
                    label
                    for label in (_norm_label(x) for x in self.required_capabilities)
                    if label
                )
            )[:32],
            failure_classes=tuple(
                dict.fromkeys(
                    label
                    for label in (_norm_label(x) for x in self.failure_classes)
                    if label
                )
            )[:32],
            uncertainty=_safe_unit(self.uncertainty),
            novelty=_safe_unit(self.novelty),
            verifier_disagreement=_safe_unit(self.verifier_disagreement),
            available_routes=tuple(
                dict.fromkeys(
                    label
                    for label in (_norm_label(x) for x in self.available_routes)
                    if label
                )
            )[:256],
            route_hints=tuple(
                (
                    route_id,
                    score,
                )
                for route_id, score in (
                    (
                        _norm_label(item[0]),
                        _safe_unit(item[1]),
                    )
                    for item in self.route_hints[:256]
                    if isinstance(item, (tuple, list)) and len(item) == 2
                )
                if route_id
            ),
        )


@dataclass
class RouteLearningState:
    route_id: str
    visits: int = 0
    successes: int = 0
    failures: int = 0
    reward_sum: float = 0.0
    latency_sum: float = 0.0
    utility_ema: float = 0.55
    family_affinity: dict[str, float] = field(default_factory=dict)
    form_affinity: dict[str, float] = field(default_factory=dict)
    capability_affinity: dict[str, float] = field(default_factory=dict)
    failure_affinity: dict[str, float] = field(default_factory=dict)

    @property
    def mean_reward(self) -> float:
        if self.visits <= 0:
            return self.utility_ema
        return self.reward_sum / self.visits

    @property
    def mean_latency(self) -> float:
        if self.visits <= 0:
            return 0.0
        return self.latency_sum / self.visits


@dataclass
class SparseEdge:
    source: str
    target: str
    weight: float
    active: bool
    visits: int = 0
    successes: int = 0
    failures: int = 0
    last_used_step: int = 0
    last_changed_step: int = 0


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    base_score: float
    propagated_score: float
    final_score: float
    graph_neighbors_used: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RoutePath:
    route_ids: tuple[str, ...]
    score: float
    verification_covered: bool
    failure_specialty_covered: bool
    transition_mean: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RoutingDecision:
    version: str
    step: int
    density: float
    target_density: float
    selected: tuple[RouteCandidate, ...]
    primary_path: RoutePath
    alternative_paths: tuple[RoutePath, ...]
    active_edges: int
    possible_edges: int
    densified: bool
    sparsified: bool
    rewired: bool
    context: RoutingContext

    def to_dict(self) -> dict:
        out = asdict(self)
        out["context"] = asdict(self.context)
        out["selected"] = [item.to_dict() for item in self.selected]
        out["primary_path"] = self.primary_path.to_dict()
        out["alternative_paths"] = [
            item.to_dict() for item in self.alternative_paths
        ]
        return out


@dataclass(frozen=True)
class RoutingFeedback:
    selected_route_ids: tuple[str, ...]
    reward: float
    verified: bool
    latency: float = 0.0
    successful_route_id: str = ""
    context: RoutingContext = RoutingContext()

    def normalized(self) -> "RoutingFeedback":
        routes = tuple(
            dict.fromkeys(
                route
                for route in (_norm_label(x) for x in self.selected_route_ids)
                if route
            )
        )[:64]
        winner = _norm_label(self.successful_route_id)
        try:
            latency = float(self.latency)
        except (TypeError, ValueError, OverflowError):
            latency = 0.0
        if not isfinite(latency):
            latency = 0.0
        return RoutingFeedback(
            selected_route_ids=routes,
            reward=_safe_unit(self.reward),
            verified=bool(self.verified),
            latency=max(0.0, latency),
            successful_route_id=winner,
            context=self.context.normalized(),
        )


class DynamicSparseRouter:
    """Generic dynamic-sparse route graph for FAP public mainline.

    The graph intentionally starts slightly dense so several reusable reasoning
    paths can compete. After warm-up, weak edges decay and are pruned toward a
    sparse target. High uncertainty, novelty, verifier disagreement, or repeated
    failure temporarily raises the target density and can reactivate dormant
    edges. No benchmark item text, IDs, answers, or answer fingerprints are
    stored by this router.
    """

    VERSION = "fap.dynamic_sparse_router.v1"

    def __init__(
        self,
        routes: Iterable[RouteSpec],
        *,
        config: DynamicSparseConfig | None = None,
        seed: str = "fap-1.0.01",
    ) -> None:
        self.config = config or DynamicSparseConfig()
        self.seed = str(seed or "fap-1.0.01")
        route_rows = tuple(routes)
        if len(route_rows) < 2:
            raise ValueError("at least two routes are required")
        if len(route_rows) > 256:
            raise ValueError("route count must not exceed 256")

        self.routes: dict[str, RouteSpec] = {}
        for route in route_rows:
            if route.route_id in self.routes:
                raise ValueError(f"duplicate route_id: {route.route_id}")
            self.routes[route.route_id] = route

        self.state: dict[str, RouteLearningState] = {
            route_id: RouteLearningState(
                route_id=route_id,
                utility_ema=float(spec.prior_quality),
            )
            for route_id, spec in self.routes.items()
        }
        self.edges: dict[tuple[str, str], SparseEdge] = {}
        self.step = 0
        self._build_initial_graph()

    @property
    def possible_edges(self) -> int:
        count = len(self.routes)
        return count * (count - 1)

    @property
    def active_edges(self) -> int:
        return sum(1 for edge in self.edges.values() if edge.active)

    @property
    def density(self) -> float:
        total = self.possible_edges
        return self.active_edges / total if total else 0.0

    def _build_initial_graph(self) -> None:
        route_ids = tuple(sorted(self.routes))
        for source in route_ids:
            for target in route_ids:
                if source == target:
                    continue
                prior = 0.34 + 0.42 * _stable_unit(
                    self.seed,
                    "edge",
                    source,
                    target,
                )
                self.edges[(source, target)] = SparseEdge(
                    source=source,
                    target=target,
                    weight=prior,
                    active=False,
                )

        # Keep the *realized* initial graph close to initial_density. Using an
        # independent Bernoulli decision and then forcing a minimum degree can
        # accidentally create a much denser graph on small route sets.
        degree = max(
            1,
            min(
                len(route_ids) - 1,
                max(
                    self.config.min_initial_degree,
                    int(round((len(route_ids) - 1) * self.config.initial_density)),
                ),
            ),
        )
        for source in route_ids:
            outgoing = sorted(
                (
                    edge
                    for (src, _), edge in self.edges.items()
                    if src == source
                ),
                key=lambda edge: (
                    -(
                        0.70 * edge.weight
                        + 0.30 * _stable_unit(
                            self.seed,
                            "initial_select",
                            source,
                            edge.target,
                        )
                    ),
                    edge.target,
                ),
            )
            for edge in outgoing[:degree]:
                edge.active = True

    def _failure_pressure(self, context: RoutingContext) -> float:
        count_pressure = min(1.0, len(context.failure_classes) / 4.0)
        return _clamp(
            0.45 * count_pressure
            + 0.35 * context.verifier_disagreement
            + 0.20 * context.uncertainty,
            0.0,
            1.0,
        )

    def _target_density(self, context: RoutingContext) -> float:
        if self.step < self.config.warmup_steps:
            return self.config.initial_density
        failure = self._failure_pressure(context)
        risk = _clamp(
            0.40 * context.uncertainty
            + 0.30 * context.novelty
            + 0.30 * failure,
            0.0,
            1.0,
        )
        return _clamp(
            self.config.sparse_target + 0.16 * risk,
            self.config.sparse_floor,
            self.config.initial_density,
        )

    @staticmethod
    def _affinity(table: Mapping[str, float], key: str) -> float:
        if not key:
            return 0.5
        return _clamp(table.get(key, 0.5), 0.0, 1.0)

    def _route_base_score(
        self,
        route: RouteSpec,
        context: RoutingContext,
    ) -> tuple[float, tuple[str, ...]]:
        learning = self.state[route.route_id]
        reasons: list[str] = []

        available = set(context.available_routes)
        if available and route.route_id not in available:
            return -1_000_000.0, ("unavailable_for_turn",)

        quality = _clamp(
            0.42 * float(route.prior_quality)
            + 0.58 * learning.utility_ema,
            0.0,
            1.0,
        )
        score = 0.45 * quality
        reasons.append(f"quality={quality:.3f}")

        if context.task_family:
            declared = context.task_family in route.task_families
            learned = self._affinity(learning.family_affinity, context.task_family)
            family = _clamp(0.65 * float(declared) + 0.35 * learned, 0.0, 1.0)
            score += 0.14 * family
            reasons.append(f"family={family:.3f}")

        if context.task_form:
            declared = context.task_form in route.task_forms
            learned = self._affinity(learning.form_affinity, context.task_form)
            form = _clamp(0.65 * float(declared) + 0.35 * learned, 0.0, 1.0)
            score += 0.12 * form
            reasons.append(f"form={form:.3f}")

        if context.required_capabilities:
            declared = set(route.capabilities)
            matches = sum(1 for cap in context.required_capabilities if cap in declared)
            declared_ratio = matches / len(context.required_capabilities)
            learned_ratio = sum(
                self._affinity(learning.capability_affinity, cap)
                for cap in context.required_capabilities
            ) / len(context.required_capabilities)
            capability = _clamp(
                0.70 * declared_ratio + 0.30 * learned_ratio,
                0.0,
                1.0,
            )
            score += 0.16 * capability
            reasons.append(f"capability={capability:.3f}")

        if context.failure_classes:
            declared = set(route.failure_specialties)
            matches = sum(1 for failure in context.failure_classes if failure in declared)
            declared_ratio = matches / len(context.failure_classes)
            learned_ratio = sum(
                self._affinity(learning.failure_affinity, failure)
                for failure in context.failure_classes
            ) / len(context.failure_classes)
            failure_fit = _clamp(
                0.62 * declared_ratio + 0.38 * learned_ratio,
                0.0,
                1.0,
            )
            score += 0.10 * failure_fit
            reasons.append(f"failure_fit={failure_fit:.3f}")

        hint_map = dict(context.route_hints)
        if route.route_id in hint_map:
            hint = _safe_unit(hint_map[route.route_id])
            score += 0.32 * hint
            reasons.append(f"turn_hint={hint:.3f}")

        exploration = self.config.exploration_floor
        if learning.visits == 0:
            exploration += 0.12
        else:
            total_visits = 1 + sum(item.visits for item in self.state.values())
            exploration += self.config.exploration_strength * sqrt(
                log(total_visits + 1.0) / (learning.visits + 1.0)
            )
        exploration *= 0.55 + 0.45 * max(context.novelty, context.uncertainty)
        score += min(0.18, exploration)
        reasons.append(f"explore={min(0.18, exploration):.3f}")

        cost_penalty = self.config.cost_penalty * log(1.0 + float(route.cost))
        score -= cost_penalty
        reasons.append(f"cost=-{cost_penalty:.3f}")

        return score, tuple(reasons)

    def _propagate(
        self,
        base_scores: Mapping[str, float],
    ) -> tuple[dict[str, float], dict[str, int]]:
        current = dict(base_scores)
        neighbor_counts = {route_id: 0 for route_id in self.routes}
        for _ in range(self.config.propagation_hops):
            incoming = {route_id: 0.0 for route_id in self.routes}
            counts = {route_id: 0 for route_id in self.routes}
            for edge in self.edges.values():
                if not edge.active:
                    continue
                source_score = max(0.0, current.get(edge.source, 0.0))
                incoming[edge.target] += source_score * edge.weight
                counts[edge.target] += 1
            next_scores: dict[str, float] = {}
            for route_id in self.routes:
                if counts[route_id]:
                    propagated = incoming[route_id] / counts[route_id]
                    neighbor_counts[route_id] = max(
                        neighbor_counts[route_id],
                        counts[route_id],
                    )
                else:
                    propagated = 0.0
                next_scores[route_id] = (
                    base_scores[route_id]
                    + self.config.propagation_gain * propagated
                )
            current = next_scores
        return current, neighbor_counts

    def _path_length_for_context(self, context: RoutingContext) -> int:
        risk = max(
            context.uncertainty,
            context.novelty,
            context.verifier_disagreement,
            self._failure_pressure(context),
        )
        if risk >= 0.78:
            return min(self.config.max_path_length, 4)
        if risk >= 0.48:
            return min(self.config.max_path_length, 3)
        if risk >= 0.22:
            return min(self.config.max_path_length, 2)
        return 1

    def _path_features(
        self,
        route_ids: tuple[str, ...],
        context: RoutingContext,
    ) -> tuple[bool, bool, float]:
        verification = any(
            "verification" in self.routes[route_id].capabilities
            or "counterexample" in self.routes[route_id].capabilities
            for route_id in route_ids
        )
        failures = set(context.failure_classes)
        failure_covered = (
            not failures
            or any(
                failures & set(self.routes[route_id].failure_specialties)
                for route_id in route_ids
            )
        )
        transitions = [
            self.edges[(source, target)].weight
            for source, target in zip(route_ids, route_ids[1:])
            if (source, target) in self.edges
        ]
        transition_mean = (
            sum(transitions) / len(transitions)
            if transitions
            else 0.0
        )
        return verification, failure_covered, transition_mean

    def _path_score(
        self,
        route_ids: tuple[str, ...],
        node_scores: Mapping[str, float],
        context: RoutingContext,
    ) -> float:
        node_mean = sum(node_scores[route_id] for route_id in route_ids) / len(route_ids)
        verification, failure_covered, transition_mean = self._path_features(
            route_ids,
            context,
        )
        score = 0.72 * node_mean + 0.28 * transition_mean

        verify_need = max(
            context.uncertainty,
            context.verifier_disagreement,
        )
        if verification:
            score += 0.12 * verify_need
        elif verify_need >= 0.55:
            score -= 0.10 * verify_need

        if context.failure_classes:
            score += 0.08 if failure_covered else -0.08

        # Mildly prefer shorter routes when evidence is equal.
        score -= 0.015 * max(0, len(route_ids) - 1)
        return score

    def _plan_paths(
        self,
        node_scores: Mapping[str, float],
        context: RoutingContext,
    ) -> tuple[RoutePath, tuple[RoutePath, ...]]:
        target_length = self._path_length_for_context(context)
        available = set(context.available_routes) or set(self.routes)
        starts = sorted(
            (route_id for route_id in self.routes if route_id in available),
            key=lambda route_id: (-node_scores[route_id], route_id),
        )[: self.config.path_beam_width]
        beam: list[tuple[str, ...]] = [(route_id,) for route_id in starts]

        for _ in range(1, target_length):
            expanded: list[tuple[str, ...]] = []
            for path in beam:
                source = path[-1]
                outgoing = sorted(
                    (
                        edge
                        for edge in self.edges.values()
                        if edge.active
                        and edge.source == source
                        and edge.target not in path
                        and edge.target in available
                    ),
                    key=lambda edge: (
                        -(
                            0.55 * edge.weight
                            + 0.45 * node_scores[edge.target]
                        ),
                        edge.target,
                    ),
                )
                if not outgoing:
                    expanded.append(path)
                    continue
                for edge in outgoing[: self.config.path_beam_width]:
                    expanded.append(path + (edge.target,))
            if not expanded:
                break
            expanded.sort(
                key=lambda path: (
                    -self._path_score(path, node_scores, context),
                    path,
                )
            )
            beam = expanded[: self.config.path_beam_width]

        ranked = sorted(
            beam,
            key=lambda path: (
                -self._path_score(path, node_scores, context),
                path,
            ),
        )
        if not ranked:
            fallback = (max(node_scores, key=node_scores.get),)
            ranked = [fallback]

        rows: list[RoutePath] = []
        for path in ranked[: self.config.path_alternatives]:
            verification, failure_covered, transition_mean = self._path_features(
                path,
                context,
            )
            rows.append(
                RoutePath(
                    route_ids=path,
                    score=self._path_score(path, node_scores, context),
                    verification_covered=verification,
                    failure_specialty_covered=failure_covered,
                    transition_mean=transition_mean,
                )
            )
        return rows[0], tuple(rows[1:])

    def _edge_context_value(
        self,
        edge: SparseEdge,
        context: RoutingContext,
    ) -> float:
        available = set(context.available_routes)
        if available and (
            edge.source not in available or edge.target not in available
        ):
            return 0.0
        target = self.routes[edge.target]
        score = 0.0
        weight = 0.0

        if context.required_capabilities:
            required = set(context.required_capabilities)
            match = len(required & set(target.capabilities)) / len(required)
            score += 0.45 * match
            weight += 0.45

        if context.failure_classes:
            failures = set(context.failure_classes)
            match = len(failures & set(target.failure_specialties)) / len(failures)
            score += 0.30 * match
            weight += 0.30

        verify_need = max(
            context.uncertainty,
            context.verifier_disagreement,
        )
        if verify_need > 0.0:
            verification_capable = (
                "verification" in target.capabilities
                or "counterexample" in target.capabilities
            )
            score += 0.25 * verify_need * float(verification_capable)
            weight += 0.25

        if weight <= 0.0:
            return 0.5
        return _clamp(score / weight, 0.0, 1.0)

    def _reactivate_for_context(
        self,
        context: RoutingContext,
        desired_density: float,
    ) -> bool:
        desired = int(round(self.possible_edges * desired_density))
        missing = max(0, desired - self.active_edges)
        if missing <= 0:
            return False

        pressure = max(
            context.uncertainty,
            context.novelty,
            context.verifier_disagreement,
            self._failure_pressure(context),
        )
        if pressure < self.config.reactivate_threshold:
            return False

        budget = min(self.config.reactivation_budget, missing)
        dormant = [edge for edge in self.edges.values() if not edge.active]
        dormant.sort(
            key=lambda edge: (
                -(
                    0.35 * edge.weight
                    + 0.35 * self._edge_context_value(edge, context)
                    + 0.15 * _clamp(
                        self._route_base_score(
                            self.routes[edge.target],
                            context,
                        )[0],
                        0.0,
                        1.0,
                    )
                    + 0.15 * _stable_unit(
                        self.seed,
                        "reactivate",
                        str(self.step),
                        edge.source,
                        edge.target,
                    )
                ),
                edge.source,
                edge.target,
            )
        )
        for edge in dormant[:budget]:
            edge.active = True
            edge.last_changed_step = self.step
        return bool(dormant[:budget])

    def _rewire_for_context(self, context: RoutingContext) -> bool:
        pressure = max(
            context.uncertainty,
            context.novelty,
            context.verifier_disagreement,
            self._failure_pressure(context),
        )
        if pressure < self.config.reactivate_threshold:
            return False

        outgoing_counts: dict[str, int] = {
            route_id: sum(
                1
                for edge in self.edges.values()
                if edge.active and edge.source == route_id
            )
            for route_id in self.routes
        }

        def contextual_score(edge: SparseEdge) -> float:
            return (
                0.35 * self._edge_context_value(edge, context)
                + 0.30 * edge.weight
                + 0.20 * _clamp(
                    self._route_base_score(
                        self.routes[edge.target],
                        context,
                    )[0],
                    0.0,
                    1.0,
                )
                + 0.15 * _stable_unit(
                    self.seed,
                    "rewire",
                    str(self.step),
                    edge.source,
                    edge.target,
                )
            )

        dormant = sorted(
            (edge for edge in self.edges.values() if not edge.active),
            key=lambda edge: (
                -contextual_score(edge),
                edge.source,
                edge.target,
            ),
        )
        active = sorted(
            (
                edge
                for edge in self.edges.values()
                if edge.active and outgoing_counts[edge.source] > 1
            ),
            key=lambda edge: (
                contextual_score(edge),
                edge.weight,
                edge.source,
                edge.target,
            ),
        )

        swaps = 0
        max_swaps = max(1, self.config.reactivation_budget // 2)
        used_active: set[tuple[str, str]] = set()
        for new_edge in dormant:
            if swaps >= max_swaps:
                break
            new_score = contextual_score(new_edge)
            replacement = None
            for old_edge in active:
                key = (old_edge.source, old_edge.target)
                if key in used_active:
                    continue
                if outgoing_counts[old_edge.source] <= 1:
                    continue
                old_score = contextual_score(old_edge)
                if new_score <= old_score + 0.08:
                    continue
                replacement = old_edge
                break
            if replacement is None:
                continue

            replacement.active = False
            replacement.last_changed_step = self.step
            outgoing_counts[replacement.source] -= 1
            used_active.add((replacement.source, replacement.target))

            new_edge.active = True
            new_edge.last_changed_step = self.step
            outgoing_counts[new_edge.source] += 1
            swaps += 1

        return swaps > 0

    def _sparsify(self, target_density: float) -> bool:
        if self.step < self.config.warmup_steps:
            return False
        target_edges = max(
            len(self.routes),  # preserve at least one outgoing edge per route
            int(round(self.possible_edges * target_density)),
        )
        if self.active_edges <= target_edges:
            return False

        candidates = [
            edge
            for edge in self.edges.values()
            if edge.active
        ]
        candidates.sort(
            key=lambda edge: (
                edge.weight > self.config.prune_threshold,
                edge.weight,
                edge.visits,
                edge.last_used_step,
                edge.source,
                edge.target,
            )
        )

        outgoing_counts: dict[str, int] = {
            route_id: sum(
                1
                for edge in self.edges.values()
                if edge.active and edge.source == route_id
            )
            for route_id in self.routes
        }
        removed = 0
        for edge in candidates:
            if self.active_edges <= target_edges:
                break
            if outgoing_counts[edge.source] <= 1:
                continue
            # Prune by relative rank, not by an absolute gate. The initial
            # weights intentionally start above prune_threshold, so an absolute
            # cutoff alone would make the graph impossible to sparsify.
            edge.active = False
            edge.last_changed_step = self.step
            outgoing_counts[edge.source] -= 1
            removed += 1
        return removed > 0

    def select(
        self,
        context: RoutingContext,
        *,
        top_k: int = 4,
    ) -> RoutingDecision:
        context = context.normalized()
        k = min(
            self.config.max_selected_routes,
            max(1, int(top_k)),
            len(self.routes),
        )
        target_density = self._target_density(context)
        # Finalize topology before scoring paths. A route path must never be
        # selected over an edge that is pruned later in the same decision.
        sparsified = self._sparsify(target_density)
        densified = self._reactivate_for_context(context, target_density)
        rewired = self._rewire_for_context(context)

        base_scores: dict[str, float] = {}
        reasons: dict[str, tuple[str, ...]] = {}
        for route_id, route in self.routes.items():
            score, route_reasons = self._route_base_score(route, context)
            base_scores[route_id] = score
            reasons[route_id] = route_reasons

        propagated, neighbors = self._propagate(base_scores)
        ranked: list[RouteCandidate] = []
        available = set(context.available_routes) or set(self.routes)
        for route_id in self.routes:
            if route_id not in available:
                continue
            final = propagated[route_id]
            ranked.append(
                RouteCandidate(
                    route_id=route_id,
                    base_score=base_scores[route_id],
                    propagated_score=propagated[route_id],
                    final_score=final,
                    graph_neighbors_used=neighbors[route_id],
                    reasons=reasons[route_id],
                )
            )
        ranked.sort(key=lambda item: (-item.final_score, item.route_id))
        primary_path, alternative_paths = self._plan_paths(
            propagated,
            context,
        )

        return RoutingDecision(
            version=self.VERSION,
            step=self.step,
            density=self.density,
            target_density=target_density,
            selected=tuple(ranked[:k]),
            primary_path=primary_path,
            alternative_paths=alternative_paths,
            active_edges=self.active_edges,
            possible_edges=self.possible_edges,
            densified=densified,
            sparsified=sparsified,
            rewired=rewired,
            context=context,
        )

    @staticmethod
    def _update_affinity(
        table: dict[str, float],
        keys: Iterable[str],
        reward: float,
        lr: float,
    ) -> None:
        for key in keys:
            if not key:
                continue
            old = _clamp(table.get(key, 0.5), 0.0, 1.0)
            table[key] = _clamp(old + lr * (reward - old), 0.0, 1.0)

    def observe(self, feedback: RoutingFeedback) -> None:
        row = feedback.normalized()
        if not row.selected_route_ids:
            raise ValueError("feedback requires at least one selected route")
        missing = [route for route in row.selected_route_ids if route not in self.routes]
        if missing:
            raise ValueError(f"unknown route_id in feedback: {missing[0]}")
        if (
            row.successful_route_id
            and row.successful_route_id not in row.selected_route_ids
        ):
            raise ValueError("successful_route_id must be one of selected_route_ids")

        self.step += 1
        reward = row.reward
        winner = row.successful_route_id if row.successful_route_id in self.routes else ""

        for learning in self.state.values():
            learning.utility_ema = _clamp(
                self.config.node_decay * learning.utility_ema
                + (1.0 - self.config.node_decay) * 0.5,
                0.0,
                1.0,
            )

        for route_id in row.selected_route_ids:
            learning = self.state[route_id]
            learning.visits += 1
            learning.reward_sum += reward
            learning.latency_sum += row.latency
            if row.verified:
                learning.successes += 1
                participation = max(0.55, reward * 0.78)
                target = (
                    max(reward, 0.78)
                    if winner and winner == route_id
                    else participation
                )
                lr = (
                    self.config.success_lr
                    if not winner or winner == route_id
                    else self.config.success_lr * 0.55
                )
            else:
                learning.failures += 1
                target = min(reward, 0.35)
                lr = self.config.failure_lr
            learning.utility_ema = _clamp(
                learning.utility_ema + lr * (target - learning.utility_ema),
                0.0,
                1.0,
            )
            self._update_affinity(
                learning.family_affinity,
                (row.context.task_family,),
                target,
                lr,
            )
            self._update_affinity(
                learning.form_affinity,
                (row.context.task_form,),
                target,
                lr,
            )
            self._update_affinity(
                learning.capability_affinity,
                row.context.required_capabilities,
                target,
                lr,
            )
            self._update_affinity(
                learning.failure_affinity,
                row.context.failure_classes,
                target,
                lr,
            )

        for edge in self.edges.values():
            edge.weight = _clamp(
                0.5 + self.config.edge_decay * (edge.weight - 0.5),
                0.05,
                0.95,
            )

        chain = row.selected_route_ids
        for source, target in zip(chain, chain[1:]):
            edge = self.edges.get((source, target))
            if edge is None:
                continue
            edge.visits += 1
            edge.last_used_step = self.step
            # A verified multi-route chain should reinforce the transition
            # itself even when a particular node is marked as the final winner.
            positive = row.verified
            if positive:
                edge.successes += 1
                edge.weight = _clamp(
                    edge.weight
                    + self.config.success_lr * (1.0 - edge.weight),
                    0.05,
                    0.95,
                )
                edge.active = True
            else:
                edge.failures += 1
                edge.weight = _clamp(
                    edge.weight
                    - self.config.failure_lr * edge.weight,
                    0.05,
                    0.95,
                )
            edge.last_changed_step = self.step

        target_density = self._target_density(row.context)
        self._reactivate_for_context(row.context, target_density)
        self._sparsify(target_density)

    @staticmethod
    def _bounded_affinity_payload(
        table: Mapping[str, float],
    ) -> dict[str, float]:
        rows = []
        for raw_key, raw_value in table.items():
            key = _norm_label(raw_key)
            if not key:
                continue
            rows.append((key, _safe_unit(raw_value, default=0.5)))
        rows.sort(key=lambda item: item[0])
        return dict(rows[:128])

    def _route_schema_digest(self) -> str:
        payload = [
            {
                "route_id": route.route_id,
                "capabilities": list(route.capabilities),
                "task_families": list(route.task_families),
                "task_forms": list(route.task_forms),
                "failure_specialties": list(route.failure_specialties),
                "prior_quality": float(route.prior_quality),
                "cost": float(route.cost),
            }
            for route in (
                self.routes[route_id]
                for route_id in sorted(self.routes)
            )
        ]
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def export_learning_state(self) -> dict:
        routes: dict[str, dict] = {}
        for route_id in sorted(self.routes):
            state = self.state[route_id]
            routes[route_id] = {
                "visits": min(1_000_000_000, max(0, int(state.visits))),
                "successes": min(1_000_000_000, max(0, int(state.successes))),
                "failures": min(1_000_000_000, max(0, int(state.failures))),
                "reward_sum": max(0.0, float(state.reward_sum)),
                "latency_sum": max(0.0, float(state.latency_sum)),
                "utility_ema": _safe_unit(state.utility_ema, default=0.5),
                "family_affinity": self._bounded_affinity_payload(
                    state.family_affinity
                ),
                "form_affinity": self._bounded_affinity_payload(
                    state.form_affinity
                ),
                "capability_affinity": self._bounded_affinity_payload(
                    state.capability_affinity
                ),
                "failure_affinity": self._bounded_affinity_payload(
                    state.failure_affinity
                ),
            }

        edges = []
        for key in sorted(self.edges):
            edge = self.edges[key]
            edges.append(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "weight": _clamp(edge.weight, 0.05, 0.95),
                    "active": bool(edge.active),
                    "visits": min(1_000_000_000, max(0, int(edge.visits))),
                    "successes": min(1_000_000_000, max(0, int(edge.successes))),
                    "failures": min(1_000_000_000, max(0, int(edge.failures))),
                    "last_used_step": min(
                        1_000_000_000,
                        max(0, int(edge.last_used_step)),
                    ),
                    "last_changed_step": min(
                        1_000_000_000,
                        max(0, int(edge.last_changed_step)),
                    ),
                }
            )

        payload = {
            "version": "fap.dynamic_sparse_learning_state.v1",
            "router_version": self.VERSION,
            "seed": self.seed[:128],
            "route_schema_sha256": self._route_schema_digest(),
            "step": min(1_000_000_000, max(0, int(self.step))),
            "route_ids": list(sorted(self.routes)),
            "routes": routes,
            "edges": edges,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        payload["checksum_sha256"] = sha256(
            canonical.encode("utf-8")
        ).hexdigest()
        return payload

    def import_learning_state(self, payload: Mapping[str, object]) -> None:
        if not isinstance(payload, Mapping):
            raise TypeError("learning state must be a mapping")
        if payload.get("version") != "fap.dynamic_sparse_learning_state.v1":
            raise ValueError("unsupported learning state version")
        if payload.get("router_version") != self.VERSION:
            raise ValueError("learning state router version mismatch")
        if str(payload.get("seed") or "") != self.seed[:128]:
            raise ValueError("learning state seed mismatch")
        if str(payload.get("route_schema_sha256") or "") != self._route_schema_digest():
            raise ValueError("learning state route schema mismatch")

        checksum = str(payload.get("checksum_sha256") or "")
        if len(checksum) != 64:
            raise ValueError("learning state checksum missing")
        unsigned = dict(payload)
        unsigned.pop("checksum_sha256", None)
        canonical = json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        expected = sha256(canonical.encode("utf-8")).hexdigest()
        if checksum != expected:
            raise ValueError("learning state checksum mismatch")

        route_ids = payload.get("route_ids")
        if not isinstance(route_ids, list):
            raise ValueError("learning state route_ids invalid")
        if tuple(route_ids) != tuple(sorted(self.routes)):
            raise ValueError("learning state route set mismatch")

        step = int(payload.get("step", 0))
        if not 0 <= step <= 1_000_000_000:
            raise ValueError("learning state step invalid")

        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, Mapping):
            raise ValueError("learning state routes invalid")

        def parse_count(value: object) -> int:
            number = int(value)
            if not 0 <= number <= 1_000_000_000:
                raise ValueError("learning state count invalid")
            return number

        def parse_nonnegative(value: object) -> float:
            number = float(value)
            if not isfinite(number) or number < 0.0:
                raise ValueError("learning state numeric value invalid")
            return number

        def parse_affinity(value: object) -> dict[str, float]:
            if not isinstance(value, Mapping) or len(value) > 128:
                raise ValueError("learning state affinity invalid")
            out: dict[str, float] = {}
            for raw_key, raw_score in value.items():
                key = _norm_label(raw_key)
                if not key or key != str(raw_key):
                    raise ValueError("learning state affinity key invalid")
                score = float(raw_score)
                if not isfinite(score) or not 0.0 <= score <= 1.0:
                    raise ValueError("learning state affinity score invalid")
                out[key] = score
            return out

        new_states: dict[str, RouteLearningState] = {}
        for route_id in sorted(self.routes):
            raw = raw_routes.get(route_id)
            if not isinstance(raw, Mapping):
                raise ValueError("learning state route row invalid")
            new_states[route_id] = RouteLearningState(
                route_id=route_id,
                visits=parse_count(raw.get("visits", 0)),
                successes=parse_count(raw.get("successes", 0)),
                failures=parse_count(raw.get("failures", 0)),
                reward_sum=parse_nonnegative(raw.get("reward_sum", 0.0)),
                latency_sum=parse_nonnegative(raw.get("latency_sum", 0.0)),
                utility_ema=_safe_unit(raw.get("utility_ema"), default=0.5),
                family_affinity=parse_affinity(
                    raw.get("family_affinity", {})
                ),
                form_affinity=parse_affinity(
                    raw.get("form_affinity", {})
                ),
                capability_affinity=parse_affinity(
                    raw.get("capability_affinity", {})
                ),
                failure_affinity=parse_affinity(
                    raw.get("failure_affinity", {})
                ),
            )

        raw_edges = payload.get("edges")
        if not isinstance(raw_edges, list):
            raise ValueError("learning state edges invalid")
        if len(raw_edges) != self.possible_edges:
            raise ValueError("learning state edge count mismatch")

        new_edges: dict[tuple[str, str], SparseEdge] = {}
        for raw in raw_edges:
            if not isinstance(raw, Mapping):
                raise ValueError("learning state edge row invalid")
            source = _norm_label(raw.get("source"))
            target = _norm_label(raw.get("target"))
            if (
                source not in self.routes
                or target not in self.routes
                or source == target
            ):
                raise ValueError("learning state edge endpoints invalid")
            key = (source, target)
            if key in new_edges:
                raise ValueError("learning state duplicate edge")
            weight = float(raw.get("weight", 0.5))
            if not isfinite(weight) or not 0.05 <= weight <= 0.95:
                raise ValueError("learning state edge weight invalid")
            new_edges[key] = SparseEdge(
                source=source,
                target=target,
                weight=weight,
                active=bool(raw.get("active", False)),
                visits=parse_count(raw.get("visits", 0)),
                successes=parse_count(raw.get("successes", 0)),
                failures=parse_count(raw.get("failures", 0)),
                last_used_step=parse_count(raw.get("last_used_step", 0)),
                last_changed_step=parse_count(
                    raw.get("last_changed_step", 0)
                ),
            )

        # Never accept a persisted topology that disconnects a source node.
        for source in self.routes:
            outgoing = [
                edge
                for (src, _), edge in new_edges.items()
                if src == source
            ]
            if not any(edge.active for edge in outgoing):
                max(outgoing, key=lambda edge: edge.weight).active = True

        self.step = step
        self.state = new_states
        self.edges = new_edges

    def snapshot(self) -> dict:
        routes = {}
        for route_id in sorted(self.routes):
            state = self.state[route_id]
            routes[route_id] = {
                "visits": state.visits,
                "successes": state.successes,
                "failures": state.failures,
                "mean_reward": state.mean_reward,
                "mean_latency": state.mean_latency,
                "utility_ema": state.utility_ema,
            }
        return {
            "version": self.VERSION,
            "step": self.step,
            "route_count": len(self.routes),
            "possible_edges": self.possible_edges,
            "active_edges": self.active_edges,
            "density": self.density,
            "config": asdict(self.config),
            "routes": routes,
        }
