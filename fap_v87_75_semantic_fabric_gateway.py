#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_74_interaction_chain_gateway as v74
from fap_code_generator import CodeGeneratorOrgan
from fap_interaction_fabric import InteractionEndpoint, InteractionRequest
from fap_repository_interaction import RepositoryCodingInteraction
from fap_repository_planner import RepositoryPlanner
from fap_semantic_fabric import SemanticFabricBridge

base = v74.base
VERSION = "87.75-unified-chat"


class FAPV8775Unified(v74.FAPV8774Unified):
    """V87.74 plus declarative semantic routes bound directly to fabric endpoints."""

    def __init__(self):
        super().__init__()
        self.semantic_fabric = SemanticFabricBridge(self.semantic_action)
        self.fabric_code_generator = CodeGeneratorOrgan(
            base.ARTIFACTS,
            base.RUNTIME / "code_v87_75",
        )
        self._mount_builtin_semantic_endpoints()

    def _mount_builtin_semantic_endpoints(self) -> None:
        self.register_semantic_endpoint(
            InteractionEndpoint(
                endpoint_id="semantic_image_generate",
                channels=("chat",),
                probe=lambda request: 0.0,
                handler=lambda request, budget: dict(
                    self.image.run_generate(request.text)
                ),
                priority=1.0,
                cost=1.0,
            ),
            ("image_generate",),
        )
        self.register_semantic_endpoint(
            InteractionEndpoint(
                endpoint_id="semantic_image_capability",
                channels=("chat",),
                probe=lambda request: 0.0,
                handler=lambda request, budget: dict(
                    self.image.run_capability()
                ),
                priority=1.0,
                cost=1.0,
            ),
            ("image_capability",),
        )
        self.register_semantic_endpoint(
            InteractionEndpoint(
                endpoint_id="artifact_code_generator",
                channels=("chat", "coding"),
                probe=lambda request: 0.0,
                handler=self._artifact_code_handler,
                priority=1.0,
                cost=1.25,
            ),
            ("artifact_code_generate",),
        )
        self.register_semantic_endpoint(
            InteractionEndpoint(
                endpoint_id="repository_inspect",
                channels=("chat", "coding"),
                probe=lambda request: 0.0,
                handler=self._repository_inspect_handler,
                priority=1.0,
                cost=1.0,
            ),
            ("repository_inspect",),
        )

    def register_semantic_endpoint(
        self,
        endpoint: InteractionEndpoint,
        route_ids: tuple[str, ...],
    ) -> None:
        self.interactions.register(
            self.semantic_fabric.bind(endpoint, route_ids)
        )

    def mount_semantic_repository_coding(
        self,
        adapter: RepositoryCodingInteraction,
        *,
        route_ids: tuple[str, ...] = ("repository_coding",),
    ) -> None:
        if not isinstance(adapter, RepositoryCodingInteraction):
            raise TypeError("adapter must be RepositoryCodingInteraction")
        self.register_semantic_endpoint(adapter.endpoint(), route_ids)

    def _artifact_code_handler(self, request: InteractionRequest, budget) -> dict:
        result = dict(
            self.fabric_code_generator.build(
                request.text,
                max_repairs=min(4, max(0, int(budget.repair_rounds))),
            )
        )
        tags = list(result.get("route_tags", []))
        for tag in (
            "semantic-fabric",
            "artifact-code-generator",
            "exponential-linear-budget",
        ):
            if tag not in tags:
                tags.append(tag)
        result["route_tags"] = tags
        result["adaptive_code_budget"] = {
            "max_repairs": min(4, max(0, int(budget.repair_rounds))),
            "scale": budget.scale,
            "demand": budget.demand,
        }
        return result

    def _repository_inspect_handler(
        self,
        request: InteractionRequest,
        budget,
    ) -> dict:
        planner = RepositoryPlanner(
            base.ROOT,
            max_files=min(32, max(4, int(budget.route_candidates))),
            max_source_bytes=min(
                1_000_000,
                max(60_000, int(budget.source_bytes)),
            ),
        )
        plan = planner.plan(request.text)
        files = [
            {
                "path": item.path,
                "operation": item.operation,
                "reason": item.reason,
            }
            for item in plan.files
        ]
        summary = ", ".join(item["path"] for item in files[:8]) or "(none)"
        return {
            "ok": plan.status == "ready",
            "reply": (
                f"Repository inspect: status={plan.status} "
                f"plan={plan.plan_id[:16]} files={summary}"
            ),
            "confidence": 0.95 if plan.status == "ready" else 0.70,
            "local": True,
            "repository_inspect": {
                "version": plan.version,
                "status": plan.status,
                "plan_id": plan.plan_id,
                "repository_digest": plan.task.repository_digest,
                "files": files,
                "required_checks": list(plan.required_checks),
                "risk_flags": list(plan.risk_flags),
                "write_enabled": False,
            },
            "route_tags": [
                "semantic-fabric",
                "repository-inspect",
                "read-only",
                "exponential-linear-budget",
            ],
        }

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.75",
            "semantic-route-to-fabric-binding",
            "declarative-code-repository-routing",
            "standalone-artifact-code-endpoint",
            "standalone-read-only-repository-inspect",
            "semantic-repository-coding-mount",
            "no-new-route-if-branches-required",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.75",
                "semantic_fabric": {
                    "enabled": True,
                    "bindings": [
                        {
                            "endpoint_id": item.endpoint_id,
                            "route_ids": list(item.route_ids),
                        }
                        for item in self.semantic_fabric.bindings
                    ],
                    "binding_count": len(self.semantic_fabric.bindings),
                    "knowledge_as_data": True,
                    "repository_coding_mountable": True,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8775Unified()
v74.CORE = CORE
v74.v73.CORE = CORE
v74.v73.v64.CORE = CORE
v74.v73.v64.v63.CORE = CORE
v74.v73.v64.v63.v62.CORE = CORE
v74.v73.v64.v63.v62.v61.CORE = CORE
v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v74.Handler):
    server_version = "FAPV87.75SemanticFabric"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.75",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.75 SEMANTIC FABRIC BINDINGS")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Semantic resource/action data now selects generic fabric endpoints.")
    print("Standalone endpoints: image, constrained artifact code, read-only repository inspect.")
    print("Repository write coding remains mountable behind existing worktree verification.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
