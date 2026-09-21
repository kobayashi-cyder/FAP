#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_47_mass_inquiry_burst_gateway as v47

base = v47.base
VERSION = "87.48-unified-chat"


class FAPV8748Unified(v47.FAPV8747Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.48",
            "question-value-ranking",
            "persistent-epistemic-ledger",
            "contradiction-quarantine",
            "persistent-unresolved-frontier",
            "verified-answer-recall",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        ledger = self.inquiry.ledger.stats()
        out.update({
            "version": VERSION,
            "mainline_version": "87.48",
            "epistemic_learning": {
                "question_value_ranking": True,
                "persistent_verified_learning": True,
                "contradiction_quarantine": True,
                "persistent_unresolved_frontier": True,
                "verified_answer_recall": True,
                "ledger": ledger,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8748Unified()
v47.CORE = CORE
v47.v46.CORE = CORE
v47.v46.v45.CORE = CORE
v47.v46.v45.v44.CORE = CORE
v47.v46.v45.v44.v43.CORE = CORE
v47.v46.v45.v44.v43.v42.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v47.Handler):
    server_version = "FAPV87.48EpistemicLearning"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.48",
                "state": "ready",
            })
            return
        if path == "/api/v1/epistemic-ledger":
            self.send_json({
                "version": VERSION,
                "stats": CORE.inquiry.ledger.stats(),
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.48 EPISTEMIC LEARNING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Inquiry questions are value-ranked before resolution.")
    print("Verified conclusions persist with source evidence IDs.")
    print("Contradictions are quarantined instead of silently overwriting knowledge.")
    print("High-value unresolved questions persist as the next-session frontier.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
