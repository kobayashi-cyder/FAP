from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re

from fap_interaction_fabric import InteractionEndpoint, InteractionRequest
from fap_semantic_action_router import SemanticActionRouter


_SAFE_ROUTE = re.compile(r"^[0-9A-Za-z_.:-]{1,128}$")


@dataclass(frozen=True)
class SemanticEndpointBinding:
    endpoint_id: str
    route_ids: tuple[str, ...]


class SemanticFabricBridge:
    """Bind declarative semantic-action routes to generic fabric endpoints."""

    def __init__(self, router: SemanticActionRouter) -> None:
        if not isinstance(router, SemanticActionRouter):
            raise TypeError("router must be SemanticActionRouter")
        self.router = router
        self._bindings: dict[str, SemanticEndpointBinding] = {}

    @property
    def bindings(self) -> tuple[SemanticEndpointBinding, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))

    def bind(
        self,
        endpoint: InteractionEndpoint,
        route_ids: tuple[str, ...],
    ) -> InteractionEndpoint:
        if not isinstance(endpoint, InteractionEndpoint):
            raise TypeError("endpoint must be InteractionEndpoint")
        routes = self._normalize_routes(route_ids)
        binding = SemanticEndpointBinding(endpoint.endpoint_id, routes)
        self._bindings[endpoint.endpoint_id] = binding

        def semantic_probe(request: InteractionRequest) -> float:
            match = self.router.match(request.text)
            if match is None:
                return 0.0
            route = str(match.get("route") or "")
            if route not in routes:
                return 0.0
            raw = float(match.get("score", 0.0))
            if not isfinite(raw) or raw <= 0.0:
                return 0.0
            return min(1.0, max(0.20, raw / 10.0))

        return InteractionEndpoint(
            endpoint_id=endpoint.endpoint_id,
            channels=endpoint.channels,
            probe=semantic_probe,
            handler=endpoint.handler,
            priority=endpoint.priority,
            cost=endpoint.cost,
        )

    def unbind(self, endpoint_id: str) -> None:
        self._bindings.pop(str(endpoint_id), None)

    @staticmethod
    def _normalize_routes(route_ids: tuple[str, ...]) -> tuple[str, ...]:
        if not isinstance(route_ids, tuple) or not route_ids:
            raise ValueError("route_ids must be a non-empty tuple")
        out: list[str] = []
        for route in route_ids:
            value = str(route or "").strip()
            if not _SAFE_ROUTE.fullmatch(value):
                raise ValueError("route_ids contains an invalid route")
            if value not in out:
                out.append(value)
        return tuple(out)
