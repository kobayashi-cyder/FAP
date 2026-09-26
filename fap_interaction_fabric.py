from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
import re
from typing import Any, Callable, Mapping

from fap_dynamic_sparse_routing import (
    DynamicSparseRouter,
    RouteSpec,
    RoutingContext,
    RoutingDecision,
    RoutingFeedback,
)
from fap_exponential_linear import (
    ExponentialLinearPolicy,
    InteractionBudget,
    InteractionDemand,
    budget_for_demand,
    estimate_interaction_demand,
)


Probe = Callable[["InteractionRequest"], float]
Handler = Callable[["InteractionRequest", InteractionBudget], Mapping[str, Any] | None]
_SAFE_ID = re.compile(r"^[0-9A-Za-z_.:-]{1,128}$")


def _history_turns(value: object) -> int:
    """Count plausible conversation turns without trusting the runtime type."""
    if value is None:
        return 0
    if isinstance(value, Mapping):
        return 1
    if isinstance(value, (str, bytes, bytearray)):
        return 0
    try:
        return max(0, int(len(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


def _safe_pressure_hint(value: object) -> float:
    """Normalize malformed external pressure hints to the neutral value."""
    try:
        hint = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not isfinite(hint):
        return 0.0
    return min(1.0, max(0.0, hint))


@dataclass(frozen=True)
class InteractionRequest:
    text: str
    history: tuple[Mapping[str, Any], ...] = ()
    channel: str = "chat"
    pressure_hint: float = 0.0
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class InteractionEndpoint:
    endpoint_id: str
    channels: tuple[str, ...]
    probe: Probe
    handler: Handler
    priority: float = 1.0
    cost: float = 1.0
    capabilities: tuple[str, ...] = ()
    task_families: tuple[str, ...] = ()
    task_forms: tuple[str, ...] = ()
    failure_specialties: tuple[str, ...] = ()


@dataclass(frozen=True)
class InteractionAttempt:
    endpoint_id: str
    score: float
    state: str
    reason: str = ""


@dataclass(frozen=True)
class InteractionDispatch:
    contract: str
    state: str
    endpoint_id: str
    demand: InteractionDemand
    budget: InteractionBudget
    attempts: tuple[InteractionAttempt, ...]
    payload: dict[str, Any] | None

    def to_dict(self) -> dict:
        return {
            "contract": self.contract,
            "state": self.state,
            "endpoint_id": self.endpoint_id,
            "demand": self.demand.to_dict(),
            "budget": self.budget.to_dict(),
            "attempts": [asdict(item) for item in self.attempts],
            "payload": dict(self.payload) if self.payload is not None else None,
        }


class InteractionFabric:
    """Provider-neutral interaction router shared by chat and coding surfaces."""

    CONTRACT = "fap.interaction.fabric.v1"

    def __init__(
        self,
        *,
        policy: ExponentialLinearPolicy | None = None,
        max_endpoints: int = 128,
    ) -> None:
        if not 1 <= int(max_endpoints) <= 1024:
            raise ValueError("max_endpoints must be in [1, 1024]")
        self.policy = policy or ExponentialLinearPolicy()
        self.max_endpoints = int(max_endpoints)
        self._endpoints: dict[str, InteractionEndpoint] = {}
        self._sparse_routers: dict[
            tuple[str, ...],
            DynamicSparseRouter,
        ] = {}

    @property
    def endpoint_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._endpoints))

    def register(self, endpoint: InteractionEndpoint) -> None:
        self._validate_endpoint(endpoint)
        if endpoint.endpoint_id not in self._endpoints and len(self._endpoints) >= self.max_endpoints:
            raise ValueError("interaction endpoint limit exceeded")
        self._endpoints[endpoint.endpoint_id] = endpoint
        self._sparse_routers.clear()

    def unregister(self, endpoint_id: str) -> None:
        self._endpoints.pop(str(endpoint_id), None)
        self._sparse_routers.clear()

    def dispatch(
        self,
        request: InteractionRequest,
        *,
        allow_endpoint_ids: tuple[str, ...] | None = None,
        exclude_endpoint_ids: tuple[str, ...] = (),
    ) -> InteractionDispatch:
        if not isinstance(request, InteractionRequest):
            raise TypeError("request must be InteractionRequest")
        allowed = self._endpoint_filter(allow_endpoint_ids, allow_none=True)
        excluded = self._endpoint_filter(exclude_endpoint_ids, allow_none=False)
        text = str(request.text or "").strip()
        channel = str(request.channel or "").strip()
        if not text:
            return self._empty_dispatch(request, "empty_request")
        if not channel or len(channel) > 64:
            return self._empty_dispatch(request, "invalid_channel")

        demand = estimate_interaction_demand(
            text,
            history_turns=_history_turns(request.history),
            pressure_hint=_safe_pressure_hint(request.pressure_hint),
        )
        budget = budget_for_demand(demand, policy=self.policy)

        ranked: list[tuple[float, str, InteractionEndpoint]] = []
        eligible_endpoints: list[InteractionEndpoint] = []
        attempts: list[InteractionAttempt] = []
        for endpoint_id in sorted(self._endpoints):
            if allowed is not None and endpoint_id not in allowed:
                continue
            if endpoint_id in excluded:
                continue
            endpoint = self._endpoints[endpoint_id]
            if channel not in endpoint.channels and "*" not in endpoint.channels:
                continue
            eligible_endpoints.append(endpoint)
            try:
                raw_score = endpoint.probe(request)
                score = float(raw_score)
                if not isfinite(score) or not 0.0 <= score <= 1.0:
                    raise ValueError("probe score out of bounds")
            except Exception as exc:
                attempts.append(
                    InteractionAttempt(
                        endpoint_id=endpoint_id,
                        score=0.0,
                        state="probe_rejected",
                        reason=f"{type(exc).__name__}",
                    )
                )
                continue
            if score <= 0.0:
                continue
            effective = score * float(endpoint.priority) / float(endpoint.cost)
            ranked.append((effective, endpoint_id, endpoint))

        ranked.sort(key=lambda row: (-row[0], row[1]))
        execution_rows = list(ranked)
        sparse_router: DynamicSparseRouter | None = None
        sparse_decision: RoutingDecision | None = None

        if len(ranked) >= 2:
            sparse_router = self._sparse_router_for(tuple(eligible_endpoints))
            if sparse_router is not None:
                max_effective = max(row[0] for row in ranked)
                route_hints = tuple(
                    (
                        endpoint_id,
                        (
                            effective / max_effective
                            if max_effective > 0.0
                            else 0.0
                        ),
                    )
                    for effective, endpoint_id, _endpoint in ranked
                )
                sparse_context = self._routing_context(
                    request,
                    route_hints=route_hints,
                    available_routes=tuple(
                        endpoint_id
                        for _effective, endpoint_id, _endpoint in ranked
                    ),
                )
                sparse_decision = sparse_router.select(
                    sparse_context,
                    top_k=min(budget.route_candidates, len(ranked)),
                )
                row_by_id = {
                    endpoint_id: (effective, endpoint_id, endpoint)
                    for effective, endpoint_id, endpoint in ranked
                }
                ordered_ids = tuple(
                    dict.fromkeys(
                        sparse_decision.primary_path.route_ids
                        + tuple(
                            item.route_id
                            for item in sparse_decision.selected
                        )
                        + tuple(
                            endpoint_id
                            for _effective, endpoint_id, _endpoint in ranked
                        )
                    )
                )
                execution_rows = [
                    row_by_id[endpoint_id]
                    for endpoint_id in ordered_ids
                    if endpoint_id in row_by_id
                ]

        executed_route_ids: list[str] = []
        for effective, endpoint_id, endpoint in execution_rows[: budget.route_candidates]:
            executed_route_ids.append(endpoint_id)
            try:
                result = endpoint.handler(request, budget)
            except Exception as exc:
                attempts.append(
                    InteractionAttempt(
                        endpoint_id=endpoint_id,
                        score=effective,
                        state="handler_failed",
                        reason=f"{type(exc).__name__}",
                    )
                )
                continue
            if result is None:
                attempts.append(
                    InteractionAttempt(
                        endpoint_id=endpoint_id,
                        score=effective,
                        state="declined",
                    )
                )
                continue
            if not isinstance(result, Mapping):
                attempts.append(
                    InteractionAttempt(
                        endpoint_id=endpoint_id,
                        score=effective,
                        state="handler_rejected",
                        reason="TypeError",
                    )
                )
                continue
            payload = dict(result)
            attempts.append(
                InteractionAttempt(
                    endpoint_id=endpoint_id,
                    score=effective,
                    state="handled",
                )
            )
            if sparse_router is not None and sparse_decision is not None:
                sparse_router.observe(
                    RoutingFeedback(
                        selected_route_ids=tuple(executed_route_ids),
                        reward=self._payload_reward(payload),
                        verified=bool(payload.get("ok", True)),
                        successful_route_id=(
                            endpoint_id
                            if bool(payload.get("ok", True))
                            else ""
                        ),
                        context=sparse_decision.context,
                    )
                )
            fabric_meta = {
                "contract": self.CONTRACT,
                "endpoint_id": endpoint_id,
                "demand": demand.value,
                "scale": budget.scale,
                "route_candidates": budget.route_candidates,
                "reasoning_steps": budget.reasoning_steps,
                "context_chars": budget.context_chars,
                "output_chars": budget.output_chars,
            }
            if sparse_router is not None and sparse_decision is not None:
                fabric_meta["dynamic_sparse"] = self._sparse_metadata(
                    sparse_router,
                    sparse_decision,
                )
            payload.setdefault("interaction_fabric", fabric_meta)
            return InteractionDispatch(
                contract=self.CONTRACT,
                state="handled",
                endpoint_id=endpoint_id,
                demand=demand,
                budget=budget,
                attempts=tuple(attempts),
                payload=payload,
            )

        if (
            sparse_router is not None
            and sparse_decision is not None
            and executed_route_ids
        ):
            sparse_router.observe(
                RoutingFeedback(
                    selected_route_ids=tuple(executed_route_ids),
                    reward=0.0,
                    verified=False,
                    context=sparse_decision.context,
                )
            )

        return InteractionDispatch(
            contract=self.CONTRACT,
            state="unhandled",
            endpoint_id="",
            demand=demand,
            budget=budget,
            attempts=tuple(attempts),
            payload=None,
        )

    @staticmethod
    def _normalized_labels(value: object) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            return ()
        out = []
        for item in value[:64]:
            if not isinstance(item, str):
                continue
            label = item.strip().casefold()
            if (
                label
                and len(label) <= 96
                and all(ch.isalnum() or ch in "_.:-" for ch in label)
            ):
                out.append(label)
        return tuple(dict.fromkeys(out))

    @staticmethod
    def _metadata_unit(metadata: Mapping[str, Any] | None, key: str) -> float:
        if not isinstance(metadata, Mapping):
            return 0.0
        try:
            value = float(metadata.get(key, 0.0))
        except (TypeError, ValueError, OverflowError):
            return 0.0
        if not isfinite(value):
            return 0.0
        return min(1.0, max(0.0, value))

    def _routing_context(
        self,
        request: InteractionRequest,
        *,
        route_hints: tuple[tuple[str, float], ...],
        available_routes: tuple[str, ...],
    ) -> RoutingContext:
        metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
        family_raw = metadata.get("task_family", request.channel)
        form_raw = metadata.get("task_form", "")
        family = (
            str(family_raw).strip().casefold()
            if isinstance(family_raw, str)
            else str(request.channel or "").strip().casefold()
        )
        form = (
            str(form_raw).strip().casefold()
            if isinstance(form_raw, str)
            else ""
        )
        return RoutingContext(
            task_family=family,
            task_form=form,
            required_capabilities=self._normalized_labels(
                metadata.get("required_capabilities", ())
            ),
            failure_classes=self._normalized_labels(
                metadata.get("failure_classes", ())
            ),
            uncertainty=max(
                _safe_pressure_hint(request.pressure_hint),
                self._metadata_unit(metadata, "uncertainty"),
            ),
            novelty=self._metadata_unit(metadata, "novelty"),
            verifier_disagreement=self._metadata_unit(
                metadata,
                "verifier_disagreement",
            ),
            available_routes=available_routes,
            route_hints=route_hints,
        )

    def _sparse_router_for(
        self,
        endpoints: tuple[InteractionEndpoint, ...],
    ) -> DynamicSparseRouter | None:
        endpoint_ids = tuple(sorted(endpoint.endpoint_id for endpoint in endpoints))
        if len(endpoint_ids) < 2:
            return None
        if any(endpoint_id != endpoint_id.casefold() for endpoint_id in endpoint_ids):
            return None
        cached = self._sparse_routers.get(endpoint_ids)
        if cached is not None:
            return cached

        specs = []
        for endpoint in sorted(endpoints, key=lambda item: item.endpoint_id):
            denominator = float(endpoint.priority) + float(endpoint.cost)
            prior_quality = (
                float(endpoint.priority) / denominator
                if denominator > 0.0
                else 0.5
            )
            specs.append(
                RouteSpec(
                    route_id=endpoint.endpoint_id,
                    capabilities=self._normalized_labels(endpoint.capabilities),
                    task_families=self._normalized_labels(endpoint.task_families),
                    task_forms=self._normalized_labels(endpoint.task_forms),
                    failure_specialties=self._normalized_labels(
                        endpoint.failure_specialties
                    ),
                    prior_quality=min(1.0, max(0.0, prior_quality)),
                    cost=float(endpoint.cost),
                )
            )
        router = DynamicSparseRouter(
            tuple(specs),
            seed="fap-1.0.01-interaction-fabric:" + "|".join(endpoint_ids),
        )
        if len(self._sparse_routers) >= 32:
            self._sparse_routers.clear()
        self._sparse_routers[endpoint_ids] = router
        return router

    @staticmethod
    def _payload_reward(payload: Mapping[str, Any]) -> float:
        try:
            confidence = float(payload.get("confidence", float("nan")))
        except (TypeError, ValueError, OverflowError):
            confidence = float("nan")
        if isfinite(confidence):
            return min(1.0, max(0.0, confidence))
        return 0.85 if bool(payload.get("ok", True)) else 0.15

    @staticmethod
    def _sparse_metadata(
        router: DynamicSparseRouter,
        decision: RoutingDecision,
    ) -> dict[str, Any]:
        return {
            "version": decision.version,
            "density": decision.density,
            "target_density": decision.target_density,
            "active_edges": decision.active_edges,
            "possible_edges": decision.possible_edges,
            "densified": decision.densified,
            "sparsified": decision.sparsified,
            "rewired": decision.rewired,
            "primary_path": list(decision.primary_path.route_ids),
            "alternative_paths": [
                list(path.route_ids)
                for path in decision.alternative_paths
            ],
            "step": router.step,
        }

    def _empty_dispatch(self, request: InteractionRequest, reason: str) -> InteractionDispatch:
        demand = estimate_interaction_demand(
            str(request.text or ""),
            history_turns=_history_turns(request.history),
            pressure_hint=_safe_pressure_hint(request.pressure_hint),
        )
        budget = budget_for_demand(demand, policy=self.policy)
        return InteractionDispatch(
            contract=self.CONTRACT,
            state="blocked",
            endpoint_id="",
            demand=demand,
            budget=budget,
            attempts=(
                InteractionAttempt(
                    endpoint_id="",
                    score=0.0,
                    state="blocked",
                    reason=reason,
                ),
            ),
            payload=None,
        )

    @staticmethod
    def _endpoint_filter(
        values: tuple[str, ...] | None,
        *,
        allow_none: bool,
    ) -> frozenset[str] | None:
        if values is None:
            if allow_none:
                return None
            raise TypeError("endpoint filter cannot be None")
        if not isinstance(values, tuple):
            raise TypeError("endpoint filter must be a tuple")
        out: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError("endpoint filter contains invalid id")
            out.add(value)
        return frozenset(out)

    @staticmethod
    def _validate_endpoint(endpoint: InteractionEndpoint) -> None:
        if not isinstance(endpoint, InteractionEndpoint):
            raise TypeError("endpoint must be InteractionEndpoint")
        if not _SAFE_ID.fullmatch(endpoint.endpoint_id):
            raise ValueError("invalid endpoint_id")
        if (
            not isinstance(endpoint.channels, tuple)
            or not endpoint.channels
            or any(not isinstance(x, str) or not x or len(x) > 64 for x in endpoint.channels)
        ):
            raise ValueError("channels must be a non-empty tuple of bounded strings")
        if not callable(endpoint.probe) or not callable(endpoint.handler):
            raise TypeError("probe and handler must be callable")
        for field_name in (
            "capabilities",
            "task_families",
            "task_forms",
            "failure_specialties",
        ):
            values = getattr(endpoint, field_name)
            if (
                not isinstance(values, tuple)
                or len(values) > 64
                or any(
                    not isinstance(value, str) or len(value) > 96
                    for value in values
                )
            ):
                raise ValueError(
                    f"{field_name} must be a bounded tuple of strings"
                )
        priority = float(endpoint.priority)
        cost = float(endpoint.cost)
        if not isfinite(priority) or priority <= 0.0:
            raise ValueError("priority must be finite and positive")
        if not isfinite(cost) or cost <= 0.0:
            raise ValueError("cost must be finite and positive")
