#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_51_literature_appraisal_gateway as v51

base = v51.base
VERSION = "87.52-unified-chat"


class FAPV8752Unified(v51.FAPV8751Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.52",
            "generic-hypothesis-generation",
            "competing-hypothesis-analysis",
            "falsification-first-reasoning",
            "prediction-derivation",
            "provisional-hypothesis-memory",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.52",
            "hypothesis_reasoning": {
                "generic": True,
                "competing_hypotheses": True,
                "predictions": True,
                "falsifiers": True,
                "next_observations": True,
                "persistent_provisional_memory": True,
                "automatic_fact_promotion": False,
                "topic_specific_router": False,
                "ledger": self.hypothesis.ledger.stats(),
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8752Unified()
v51.CORE = CORE
v51.v50.CORE = CORE
v51.v50.v49.CORE = CORE
v51.v50.v49.v48.CORE = CORE
v51.v50.v49.v48.v47.CORE = CORE
v51.v50.v49.v48.v47.v46.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v51.Handler):
    server_version = "FAPV87.52HypothesisReasoning"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.52",
                "state": "ready",
            })
            return
        if path == "/api/v1/hypotheses":
            self.send_json({
                "version": VERSION,
                "stats": CORE.hypothesis.ledger.stats(),
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.52 HYPOTHESIS + FALSIFICATION REASONING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Competing hypotheses are generated from retrieved evidence and structured models.")
    print("Each hypothesis carries predictions, falsifiers, and next observations.")
    print("Hypotheses remain provisional and are not auto-promoted to verified facts.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
