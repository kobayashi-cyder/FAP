from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
import re
from typing import Any, Callable, Mapping

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

    @property
    def endpoint_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._endpoints))

    def register(self, endpoint: InteractionEndpoint) -> None:
        self._validate_endpoint(endpoint)
        if endpoint.endpoint_id not in self._endpoints and len(self._endpoints) >= self.max_endpoints:
            raise ValueError("interaction endpoint limit exceeded")
        self._endpoints[endpoint.endpoint_id] = endpoint

    def unregister(self, endpoint_id: str) -> None:
        self._endpoints.pop(str(endpoint_id), None)

    def dispatch(self, request: InteractionRequest) -> InteractionDispatch:
        if not isinstance(request, InteractionRequest):
            raise TypeError("request must be InteractionRequest")
        text = str(request.text or "").strip()
        channel = str(request.channel or "").strip()
        if not text:
            return self._empty_dispatch(request, "empty_request")
        if not channel or len(channel) > 64:
            return self._empty_dispatch(request, "invalid_channel")

        demand = estimate_interaction_demand(
            text,
            history_turns=len(request.history),
            pressure_hint=request.pressure_hint,
        )
        budget = budget_for_demand(demand, policy=self.policy)

        ranked: list[tuple[float, str, InteractionEndpoint]] = []
        attempts: list[InteractionAttempt] = []
        for endpoint_id in sorted(self._endpoints):
            endpoint = self._endpoints[endpoint_id]
            if channel not in endpoint.channels and "*" not in endpoint.channels:
                continue
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
        for effective, endpoint_id, endpoint in ranked[: budget.route_candidates]:
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
            payload.setdefault(
                "interaction_fabric",
                {
                    "contract": self.CONTRACT,
                    "endpoint_id": endpoint_id,
                    "demand": demand.value,
                    "scale": budget.scale,
                    "route_candidates": budget.route_candidates,
                    "reasoning_steps": budget.reasoning_steps,
                    "context_chars": budget.context_chars,
                    "output_chars": budget.output_chars,
                },
            )
            return InteractionDispatch(
                contract=self.CONTRACT,
                state="handled",
                endpoint_id=endpoint_id,
                demand=demand,
                budget=budget,
                attempts=tuple(attempts),
                payload=payload,
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

    def _empty_dispatch(self, request: InteractionRequest, reason: str) -> InteractionDispatch:
        demand = estimate_interaction_demand(
            str(request.text or ""),
            history_turns=len(request.history),
            pressure_hint=request.pressure_hint,
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
        priority = float(endpoint.priority)
        cost = float(endpoint.cost)
        if not isfinite(priority) or priority <= 0.0:
            raise ValueError("priority must be finite and positive")
        if not isfinite(cost) or cost <= 0.0:
            raise ValueError("cost must be finite and positive")
