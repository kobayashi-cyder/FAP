#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_59_semantic_conversation_gateway as v59

base = v59.base
VERSION = "87.60-unified-chat"


class FAPV8760Unified(v59.FAPV8759Unified):
    """V87.59 plus current-turn relevance isolation.

    The underlying inquiry and goal-state layers now require the current turn
    to establish relevance before history can refine the answer. This prevents
    unrelated new questions from inheriting a previous topic or open goal.
    """

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.60",
            "current-turn-relevance-gate",
            "context-cannot-invent-topic",
            "goal-followup-isolation",
            "polite-request-not-persistent-goal",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.60",
            "relevance_isolation": {
                "enabled": True,
                "current_turn_first": True,
                "context_refines_only": True,
                "unrelated_goal_replan_blocked": True,
                "polite_request_goal_persistence": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8760Unified()
v59.CORE = CORE
v59.v58.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v59.Handler):
    server_version = "FAPV87.60RelevanceIsolation"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.60",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.60 CURRENT-TURN RELEVANCE ISOLATION")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("History may refine a grounded current topic, but may not invent a new topic.")
    print("Unrelated turns do not inherit stale open-goal replans.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
