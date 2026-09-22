#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_64_raster_quality_gateway as v64
from fap_exponential_linear import ExponentialLinearPolicy
from fap_interaction_fabric import (
    InteractionEndpoint,
    InteractionFabric,
    InteractionRequest,
)
from fap_repository_interaction import RepositoryCodingInteraction

base = v64.base
VERSION = "87.73-unified-chat"


class FAPV8773Unified(v64.FAPV8764Unified):
    """V87.64 plus generalized exponential-linear interaction fabric."""

    def __init__(self):
        super().__init__()
        self.interaction_policy = ExponentialLinearPolicy()
        self.interactions = InteractionFabric(policy=self.interaction_policy)
        self.interactions.register(
            InteractionEndpoint(
                endpoint_id="legacy_chat",
                channels=("chat",),
                probe=self._legacy_probe,
                handler=self._legacy_handler,
                priority=0.10,
                cost=1.0,
            )
        )

    @staticmethod
    def _legacy_probe(request: InteractionRequest) -> float:
        return 1.0 if str(request.text or "").strip() else 0.0

    def _legacy_handler(self, request: InteractionRequest, budget) -> dict:
        metadata = request.metadata or {}
        intent = metadata.get("intent")
        return super().route(intent, request.text, list(request.history))

    def register_interaction_endpoint(self, endpoint: InteractionEndpoint) -> None:
        self.interactions.register(endpoint)

    def unregister_interaction_endpoint(self, endpoint_id: str) -> None:
        if endpoint_id == "legacy_chat":
            raise ValueError("legacy_chat endpoint cannot be removed")
        self.interactions.unregister(endpoint_id)

    def mount_repository_coding(self, adapter: RepositoryCodingInteraction) -> None:
        if not isinstance(adapter, RepositoryCodingInteraction):
            raise TypeError("adapter must be RepositoryCodingInteraction")
        self.interactions.register(adapter.endpoint())

    def interaction_request_metadata(
        self,
        intent,
        text: str,
        history: list[dict],
    ) -> dict:
        return {"intent": intent}

    def interaction_pressure_hint(
        self,
        intent,
        text: str,
        history: list[dict],
    ) -> float:
        return 0.0

    def route(self, intent, text: str, history: list[dict]) -> dict:
        request = InteractionRequest(
            text=text,
            history=tuple(history or ()),
            channel="chat",
            pressure_hint=self.interaction_pressure_hint(
                intent,
                text,
                history,
            ),
            metadata=self.interaction_request_metadata(
                intent,
                text,
                history,
            ),
        )
        dispatched = self.interactions.dispatch(request)
        if dispatched.state == "handled" and dispatched.payload is not None:
            result = dict(dispatched.payload)
            result["interaction_dispatch"] = {
                "contract": dispatched.contract,
                "endpoint_id": dispatched.endpoint_id,
                "demand": dispatched.demand.value,
                "scale": dispatched.budget.scale,
                "route_candidates": dispatched.budget.route_candidates,
                "attempts": [
                    {
                        "endpoint_id": attempt.endpoint_id,
                        "state": attempt.state,
                        "reason": attempt.reason,
                    }
                    for attempt in dispatched.attempts
                ],
            }
            return result
        return super().route(intent, text, history)

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.73",
            "exponential-linear-capacity-scaling",
            "generalized-interaction-fabric",
            "dynamic-chat-endpoint-registration",
            "adaptive-repository-coding-endpoint",
            "provider-neutral-chat-code-bridge",
            "bounded-capacity-expansion",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.73",
                "interaction_fabric": {
                    "enabled": True,
                    "contract": self.interactions.CONTRACT,
                    "endpoints": list(self.interactions.endpoint_ids),
                    "endpoint_count": len(self.interactions.endpoint_ids),
                    "dynamic_registration": True,
                    "repository_coding_mountable": True,
                    "fca_required": False,
                    "policy": self.interaction_policy.to_dict(),
                    "scaling": "exponential-to-tangent-linear-with-hard-cap",
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8773Unified()
v64.CORE = CORE
v64.v63.CORE = CORE
v64.v63.v62.CORE = CORE
v64.v63.v62.v61.CORE = CORE
v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v64.Handler):
    server_version = "FAPV87.73ExponentialLinear"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.73",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.73 EXPONENTIAL-LINEAR INTERACTION FABRIC")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Chat and repository coding now share one provider-neutral interaction fabric.")
    print("Capacity scaling: exponential -> tangent-linear -> hard cap.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
