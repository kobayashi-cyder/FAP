#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_60_relevance_isolation_gateway as v60
from fap_generic_recommendation import GenericRecommendationEngine

base = v60.base
VERSION = "87.61-unified-chat"


class FAPV8761Unified(v60.FAPV8760Unified):
    """V87.60 plus generic, data-driven multi-turn recommendations."""

    def __init__(self):
        super().__init__()
        self.recommendation = GenericRecommendationEngine(base.ROOT)

    def route(self, intent, text: str, history: list[dict]) -> dict:
        recommended = self.recommendation.run(text, history)
        if recommended is not None:
            return recommended
        return super().route(intent, text, history)

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.61",
            "generic-recommendation-reasoning",
            "multi-turn-constraint-composition",
            "data-driven-candidate-ranking",
            "recommendation-context-followup",
            "no-question-specific-recommendation-branches",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.61",
            "generic_recommendation": {
                "enabled": True,
                "actions": len(self.recommendation.actions),
                "domains": len(self.recommendation.domains),
                "contexts": len(self.recommendation.contexts),
                "preferences": len(self.recommendation.preferences),
                "signals": len(self.recommendation.signals),
                "items": len(self.recommendation.items),
                "knowledge_as_data": True,
                "question_specific_branches": False,
                "multi_turn_followup": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8761Unified()
v60.CORE = CORE
v60.v59.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v60.Handler):
    server_version = "FAPV87.61GenericRecommendation"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.61",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.61 GENERIC RECOMMENDATION")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Flow: recommendation intent -> domain/context -> conversation constraints -> candidate ranking -> verify")
    print("Question-specific recommendation branches: none")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
