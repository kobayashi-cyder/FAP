#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_54_research_cycle_gateway as v54

base = v54.base
VERSION = "87.55-unified-chat"


class FAPV8755Unified(v54.FAPV8754Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.55",
            "recursive-literature-rechallenge",
            "query-refinement-by-gap-type",
            "search-saturation-stop",
            "multi-round-evidence-rechallenge",
            "research-cycle-stop-reasons",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        p = base.ROOT / "knowledge" / "research_cycle_latest.json"
        snapshot = None
        if p.exists():
            try:
                snapshot = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                snapshot = {"state": "unreadable"}
        out.update({
            "version": VERSION,
            "mainline_version": "87.55",
            "recursive_research": {
                "enabled": True,
                "snapshot_present": bool(snapshot),
                "generated_at": (snapshot or {}).get("generated_at", ""),
                "cycle_count": int((snapshot or {}).get("cycle_count", 0) or 0),
                "query_refinement_by_gap_type": True,
                "default_round_budget": 3,
                "search_saturation_stop": True,
                "automatic_fact_promotion": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8755Unified()
v54.CORE = CORE
v54.v53.CORE = CORE
v54.v53.v52.CORE = CORE
v54.v53.v52.v51.CORE = CORE
v54.v53.v52.v51.v50.CORE = CORE
v54.v53.v52.v51.v50.v49.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v54.Handler):
    server_version = "FAPV87.55RecursiveResearch"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.55",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.55 RECURSIVE RESEARCH")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Research cycles refine literature queries by unresolved gap type.")
    print("Search continues for multiple rounds and stops on saturation or strong coverage.")
    print("Evidence signals remain provisional and never auto-promote hypotheses to facts.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
