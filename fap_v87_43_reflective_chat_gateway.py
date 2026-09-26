#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_42_science_capability_gateway as v42

base = v42.base
VERSION = "87.43-unified-chat"


class FAPV8743Unified(v42.FAPV8742Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.43",
            "reflective-local-conversation",
            "knowledge-grounded-explanation",
            "causal-mechanism-chat",
            "topic-followup-resolution",
            "multi-concept-comparison",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.43",
            "reflective_chat": {
                "knowledge_grounded": True,
                "causal_explanation": True,
                "topic_followup": True,
                "multi_concept_compare": True,
                "unknowns_fail_closed": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8743Unified()
v42.CORE = CORE
v42.v41.CORE = CORE
v42.v41.v40.CORE = CORE
v42.v41.v40.v39.CORE = CORE
v42.v41.v40.v39.v38.CORE = CORE
v42.v41.v40.v39.v38.v37.CORE = CORE
v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v42.Handler):
    server_version = "FAPV87.43ReflectiveChat"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.43",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.43 REFLECTIVE LOCAL CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Known concepts are explained by mechanism, cause, boundaries and follow-up context.")
    print("Unknown factual content remains fail-closed instead of being fabricated.")
    print("V87.42 science capability, V87.41 low-latency and prior media stacks are preserved.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
