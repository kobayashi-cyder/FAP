#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_48_epistemic_learning_gateway as v48

base = v48.base
VERSION = "87.49-unified-chat"


class FAPV8749Unified(v48.FAPV8748Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.49",
            "structured-scientific-models",
            "equation-grounded-explanation",
            "mechanism-model-composition",
            "data-driven-model-growth",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.49",
            "scientific_modeling": {
                "structured_models": True,
                "equation_grounding": True,
                "mechanism_composition": True,
                "topic_specific_router": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8749Unified()
v48.CORE = CORE
v48.v47.CORE = CORE
v48.v47.v46.CORE = CORE
v48.v47.v46.v45.CORE = CORE
v48.v47.v46.v45.v44.CORE = CORE
v48.v47.v46.v45.v44.v43.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v48.Handler):
    server_version = "FAPV87.49ScientificModeling"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.49",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.49 STRUCTURED SCIENTIFIC MODELING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Scientific explanations are composed from structured model data.")
    print("Equations, variables, mechanisms, scales, assumptions and limits are exposed.")
    print("Adding scientific domains does not require new topic-specific chat branches.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
