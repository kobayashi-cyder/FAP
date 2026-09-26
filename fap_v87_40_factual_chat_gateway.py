#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_39_native_geometry_gateway as v39

base = v39.base
VERSION = "87.40-unified-chat"


class FAPV8740Unified(v39.FAPV8739Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.40",
            "direct-factual-qa",
            "factual-before-procedural-routing",
            "constraint-false-positive-guard",
            "factual-answer-verification",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.40",
            "factual_chat": {
                "direct_local_facts": True,
                "factual_before_procedural": True,
                "constraint_speed_guard": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8740Unified()
v39.CORE = CORE
v39.v38.CORE = CORE
v39.v38.v37.CORE = CORE
v39.v38.v37.v28.CORE = CORE
v39.v38.v37.v28.v27.CORE = CORE
v39.v38.v37.v28.v27.v26.CORE = CORE
v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v39.Handler):
    server_version = "FAPV87.40FactualChat"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.40",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.40 DIRECT FACTUAL CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Direct factual QA runs before procedural distilled circuits.")
    print("V87.39 native geometry/raster stack preserved.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
