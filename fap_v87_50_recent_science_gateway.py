#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_49_scientific_modeling_gateway as v49

base = v49.base
VERSION = "87.50-unified-chat"


class FAPV8750Unified(v49.FAPV8749Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.50",
            "dated-recent-science-evidence",
            "source-provenance-in-science-chat",
            "science-snapshot:2026-09-22",
            "operational-weather-science-2026",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.50",
            "recent_science": {
                "snapshot_date": "2026-09-22",
                "dated_evidence": True,
                "source_provenance": True,
                "data_driven": True,
                "auto_updates": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8750Unified()
v49.CORE = CORE
v49.v48.CORE = CORE
v49.v48.v47.CORE = CORE
v49.v48.v47.v46.CORE = CORE
v49.v48.v47.v46.v45.CORE = CORE
v49.v48.v47.v46.v45.v44.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v49.Handler):
    server_version = "FAPV87.50RecentScience"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.50",
                "state": "ready",
            })
            return
        if path == "/api/v1/science-snapshot":
            updates = CORE.scientific_model.recent_science.updates
            self.send_json({
                "version": VERSION,
                "snapshot_date": "2026-09-22",
                "count": len(updates),
                "updates": [
                    {
                        "id": u.update_id,
                        "as_of": u.as_of,
                        "institution": u.institution,
                        "title": u.title,
                        "source_title": u.source_title,
                        "source_url": u.source_url,
                        "evidence_type": u.evidence_type,
                    }
                    for u in updates
                ],
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.50 DATED RECENT SCIENCE")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Scientific answers can attach dated 2025-2026 evidence with source provenance.")
    print("Current science snapshot date: 2026-09-22.")
    print("Science updates remain data-driven under knowledge/latest_science_*.jsonl.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
