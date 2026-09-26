#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_53_research_frontier_gateway as v53

base = v53.base
VERSION = "87.54-unified-chat"


class FAPV8754Unified(v53.FAPV8753Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.54",
            "targeted-research-cycles",
            "literature-rechallenge-loop",
            "value-of-information-prioritization",
            "hypothesis-falsification-next-test",
            "rolling-autonomous-research-agenda",
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
            "mainline_version": "87.54",
            "research_cycle": {
                "enabled": True,
                "snapshot_present": bool(snapshot),
                "generated_at": (snapshot or {}).get("generated_at", ""),
                "cycle_count": int((snapshot or {}).get("cycle_count", 0) or 0),
                "papers_processed_in_frontier": int((snapshot or {}).get("papers_processed_in_frontier", 0) or 0),
                "targeted_literature_rechallenge": True,
                "value_of_information": True,
                "automatic_fact_promotion": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8754Unified()
v53.CORE = CORE
v53.v52.CORE = CORE
v53.v52.v51.CORE = CORE
v53.v52.v51.v50.CORE = CORE
v53.v52.v51.v50.v49.CORE = CORE
v53.v52.v51.v50.v49.v48.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v53.Handler):
    server_version = "FAPV87.54ResearchCycle"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.54",
                "state": "ready",
            })
            return
        if path == "/api/v1/research-cycles":
            p = base.ROOT / "knowledge" / "research_cycle_latest.json"
            if not p.exists():
                self.send_json({
                    "version": VERSION,
                    "state": "snapshot-missing",
                    "message": "The rolling literature workflow has not published a research-cycle snapshot yet.",
                })
                return
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc:
                self.send_json({
                    "version": VERSION,
                    "state": "error",
                    "error": str(exc),
                }, status=500)
                return
            self.send_json({
                "version": VERSION,
                "state": "ready",
                "research_cycles": payload,
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.54 TARGETED RESEARCH CYCLES")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Top literature gaps become value-of-information ranked research cycles.")
    print("Each cycle carries competing hypotheses, falsifiers, next tests, and targeted literature rechallenge.")
    print("Literature screening signals never auto-promote a hypothesis to verified fact.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
