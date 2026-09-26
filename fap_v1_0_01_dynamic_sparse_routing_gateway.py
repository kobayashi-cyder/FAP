#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_81_coding_conversation_gateway as v81

base = v81.base
VERSION = "1.0.01-unified-chat"


class FAPV1001Unified(v81.FAPV8781Unified):
    """Public FAP 1.0.01 candidate with dynamic-sparse interaction routing."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v1.0.01",
            "dynamic-sparse-interaction-routing",
            "mildly-dense-routing-warmup",
            "adaptive-route-sparsification",
            "risk-triggered-route-redensification",
            "context-aware-route-rewiring",
            "learned-route-utility",
            "learned-route-paths",
            "bounded-route-beam-search",
            "generic-routing-state-export-import",
            "dynamic-sparse-mechanism-benchmark",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "1.0.01",
                "dynamic_sparse_routing": {
                    "enabled": True,
                    "interaction_fabric_integrated": True,
                    "initial_density": 0.38,
                    "sparse_target": 0.22,
                    "sparse_floor": 0.16,
                    "starts_mildly_dense": True,
                    "routine_work_sparsifies": True,
                    "risk_can_redensify": True,
                    "context_can_rewire": True,
                    "learned_route_paths": True,
                    "probe_hints_preserved": True,
                    "single_route_legacy_fallback": True,
                    "generic_state_export_import": True,
                    "stores_benchmark_answers": False,
                    "fca_required": False,
                },
                "intelligence_target": {
                    "target": "GPT-5.6-Sol-class",
                    "target_is_claimed_achieved": False,
                    "task_intelligence_benchmark_complete": False,
                    "routing_mechanism_benchmark_available": True,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV1001Unified()
v81.CORE = CORE
v81.v80.CORE = CORE
v81.v80.v79.CORE = CORE
v81.v80.v79.v78.CORE = CORE
v81.v80.v79.v78.v77.CORE = CORE
v81.v80.v79.v78.v77.v76.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.v73.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.v73.v64.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v81.v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v81.Handler):
    server_version = "FAPV1.0.01DynamicSparseRouting"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "1.0.01",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP 1.0.01 DYNAMIC-SPARSE INTELLIGENT ROUTING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Interaction routing begins mildly dense and sparsifies with evidence.")
    print("Uncertainty, novelty and failure can reopen or rewire route paths.")
    print("GPT-5.6 Sol-class performance is a target, not a current benchmark claim.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
