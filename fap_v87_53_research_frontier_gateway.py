#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_52_hypothesis_reasoning_gateway as v52

base = v52.base
VERSION = "87.53-unified-chat"


class FAPV8753Unified(v52.FAPV8752Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.53",
            "literature-gap-clustering",
            "research-frontier-prioritization",
            "unresolved-question-clusters",
            "frontier-to-falsification-loop",
            "rolling-research-agenda",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        path = base.ROOT / "knowledge" / "research_frontier_latest.json"
        snapshot = None
        if path.exists():
            try:
                snapshot = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                snapshot = {"state": "unreadable"}
        out.update({
            "version": VERSION,
            "mainline_version": "87.53",
            "research_frontier": {
                "enabled": True,
                "snapshot_present": bool(snapshot),
                "snapshot_generated_at": (snapshot or {}).get("generated_at", ""),
                "papers_processed": int((snapshot or {}).get("papers_processed", 0) or 0),
                "cluster_count": int((snapshot or {}).get("cluster_count", 0) or 0),
                "literature_gap_clustering": True,
                "provisional_hypothesis_loops": True,
                "automatic_fact_promotion": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8753Unified()
v52.CORE = CORE
v52.v51.CORE = CORE
v52.v51.v50.CORE = CORE
v52.v51.v50.v49.CORE = CORE
v52.v51.v50.v49.v48.CORE = CORE
v52.v51.v50.v49.v48.v47.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v52.Handler):
    server_version = "FAPV87.53ResearchFrontier"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.53",
                "state": "ready",
            })
            return
        if path == "/api/v1/research-frontier":
            p = base.ROOT / "knowledge" / "research_frontier_latest.json"
            if not p.exists():
                self.send_json({
                    "version": VERSION,
                    "state": "snapshot-missing",
                    "message": "The rolling literature workflow has not published a local frontier snapshot yet.",
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
                "frontier": payload,
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.53 RESEARCH FRONTIER")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Large-scale unresolved appraisal items are clustered into a rolling research agenda.")
    print("Frontier items include priority questions and provisional hypothesis/falsification loops.")
    print("Missing abstract information is not treated as proof of a scientific unknown.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
