#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_50_recent_science_gateway as v50

base = v50.base
VERSION = "87.51-unified-chat"


class FAPV8751Unified(v50.FAPV8750Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.51",
            "broad-literature-screening",
            "abstract-metadata-critical-appraisal",
            "paper-question-generation",
            "paper-question-resolution",
            "crossref-rolling-review",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        summary_path = base.ROOT / "runtime" / "literature" / "latest_summary.json"
        local_summary = None
        if summary_path.exists():
            try:
                local_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                local_summary = {"state": "unreadable"}
        out.update({
            "version": VERSION,
            "mainline_version": "87.51",
            "literature_review": {
                "provider": "Crossref REST API",
                "broad_journal_article_screening": True,
                "abstract_appraisal_when_available": True,
                "formal_peer_review": False,
                "scheduled_cloud_review": True,
                "local_summary": local_summary,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8751Unified()
v50.CORE = CORE
v50.v49.CORE = CORE
v50.v49.v48.CORE = CORE
v50.v49.v48.v47.CORE = CORE
v50.v49.v48.v47.v46.CORE = CORE
v50.v49.v48.v47.v46.v45.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v50.Handler):
    server_version = "FAPV87.51LiteratureAppraisal"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.51",
                "state": "ready",
            })
            return
        if path == "/api/v1/literature-review":
            summary_path = base.ROOT / "runtime" / "literature" / "latest_summary.json"
            if not summary_path.exists():
                self.send_json({
                    "version": VERSION,
                    "state": "not-run-locally",
                    "formal_peer_review": False,
                })
                return
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
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
                "summary": summary,
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.51 BROAD LITERATURE CRITICAL APPRAISAL")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Recent journal articles can be screened from Crossref metadata.")
    print("Abstracts are critically appraised when metadata contains them.")
    print("This automated screening is not formal independent expert peer review.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
