#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer
from typing import Mapping

import fap_v87_80_multiturn_consistency_gateway as v80
from fap_response_redundancy import ResponseRedundancyPlanner

base = v80.base
VERSION = "87.81-unified-chat"


class FAPV8781Unified(v80.FAPV8780Unified):
    """V87.80 plus coding continuity and large-scale response-series redundancy."""

    def __init__(self):
        super().__init__()
        self.response_redundancy = ResponseRedundancyPlanner()

    def _pre_response_plan(self, text: str, history: list[dict]) -> dict:
        history_turns = min(128, len(history or ()))
        uncertainty = min(0.55, 0.10 + history_turns / 512.0)
        confidence = max(0.45, 0.92 - history_turns / 640.0)
        plan = self.response_redundancy.plan(
            text,
            uncertainty=uncertainty,
            confidence=confidence,
            route_candidates=1,
            verification_depth=1,
            retries=0,
            intent_count=0,
            has_route=False,
        )
        return plan.to_dict(include_lanes=False)

    def interaction_pressure_hint(
        self,
        intent,
        text: str,
        history: list[dict],
    ) -> float:
        base_hint = float(super().interaction_pressure_hint(intent, text, history))
        plan = self._pre_response_plan(text, history)
        return min(1.0, max(base_hint, float(plan.get("pressure", 0.0))))

    def interaction_request_metadata(
        self,
        intent,
        text: str,
        history: list[dict],
    ) -> dict:
        metadata = dict(super().interaction_request_metadata(intent, text, history))
        metadata["response_series_plan"] = self._pre_response_plan(text, history)
        return metadata

    def route(self, intent, text: str, history: list[dict]) -> dict:
        result = dict(super().route(intent, text, history))
        try:
            confidence = float(result.get("confidence", 0.72))
        except (TypeError, ValueError, OverflowError):
            confidence = 0.72
        confidence = min(1.0, max(0.0, confidence))

        dispatch = result.get("interaction_dispatch")
        if not isinstance(dispatch, Mapping):
            dispatch = {}
        try:
            route_candidates = int(dispatch.get("route_candidates", 1))
        except (TypeError, ValueError, OverflowError):
            route_candidates = 1

        critic = result.get("critic")
        disagreement = bool(
            isinstance(critic, Mapping)
            and (
                critic.get("issues")
                or critic.get("verdict") not in {None, "", "OK"}
            )
        )
        tags = [str(x) for x in result.get("route_tags", [])]
        counterexample = any("counterexample" in x.lower() for x in tags)

        plan = self.response_redundancy.plan(
            text,
            uncertainty=1.0 - confidence,
            confidence=confidence,
            disagreement=disagreement,
            counterexample=counterexample,
            route_candidates=route_candidates,
            verification_depth=2 if disagreement else 1,
            retries=1 if disagreement else 0,
            intent_count=0,
            has_route=bool(result.get("route") or dispatch.get("endpoint_id")),
        )
        result["response_redundancy"] = plan.to_dict()

        for tag in (
            "response-series-redundancy",
            f"response-lanes:{plan.active_lanes}",
            f"response-synthesis:{plan.synthesis_width}",
        ):
            if tag not in tags:
                tags.append(tag)
        result["route_tags"] = tags
        return result

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.81",
            "structured-multi-edit-repository-coding",
            "mixed-operation-repository-planning",
            "automatic-repository-test-selection",
            "content-free-repository-session-continuity",
            "multi-turn-coding-followup-path-affinity",
            "coding-collaboration-handoff",
            "side-branch-capability-consolidation",
            "response-series-redundancy:64-lanes",
            "response-synthesis-committee:8-max",
            "partial-salient-coverage",
            "uncertainty-adaptive-response-expansion",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.81",
                "coding_conversation": {
                    "enabled": True,
                    "structured_multi_edit": True,
                    "mixed_operation_planning": True,
                    "automatic_test_selection_available": True,
                    "repository_session_continuity": True,
                    "repository_session_stores_source_text": False,
                    "followup_path_affinity": True,
                    "fca_required": False,
                },
                "response_redundancy": {
                    "enabled": True,
                    "contract": self.response_redundancy.CONTRACT,
                    "max_lanes": self.response_redundancy.MAX_LANES,
                    "max_synthesis_width": self.response_redundancy.MAX_SYNTHESIS,
                    "adaptive_expansion": True,
                    "partial_coverage_allowed": True,
                    "coverage_target_range": [0.55, 0.90],
                    "topic_specific_branches": False,
                    "native_parity_revision": "1.0.01-cpp-native-r003",
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8781Unified()
v80.CORE = CORE
v80.v79.CORE = CORE
v80.v79.v78.CORE = CORE
v80.v79.v78.v77.CORE = CORE
v80.v79.v78.v77.v76.CORE = CORE
v80.v79.v78.v77.v76.v75.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v80.Handler):
    server_version = "FAPV87.81CodingConversation"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.81",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.81 CODING + CONVERSATION CONSOLIDATION")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Response series expand adaptively up to 64 independent lanes.")
    print("Synthesis committee expands up to 8 lanes; exhaustive coverage is not required.")
    print("Short coding follow-ups may reuse bounded prior repository paths.")
    print("Repository continuity stores hashes/path metadata only, never source text.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
