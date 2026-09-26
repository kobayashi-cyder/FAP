#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_76_session_continuity_gateway as v76

base = v76.base
VERSION = "87.77-unified-chat"


class FAPV8777Unified(v76.FAPV8776Unified):
    """V87.76 plus repository reader/planner target-context precision."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.77",
            "late-symbol-streaming-context",
            "repository-target-context-separation",
            "dependency-inspect-only-planning",
            "explicit-delete-target-required",
            "missing-explicit-target-fail-closed",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.77",
                "repository_precision": {
                    "enabled": True,
                    "late_symbol_streaming": True,
                    "dependency_context_write_target": False,
                    "delete_requires_explicit_existing_path": True,
                    "missing_explicit_target_fail_closed": True,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8777Unified()
v76.CORE = CORE
v76.v75.CORE = CORE
v76.v75.v74.CORE = CORE
v76.v75.v74.v73.CORE = CORE
v76.v75.v74.v73.v64.CORE = CORE
v76.v75.v74.v73.v64.v63.CORE = CORE
v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v76.Handler):
    server_version = "FAPV87.77RepositoryPrecision"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.77",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.77 REPOSITORY CONTEXT PRECISION")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Repository context and mutation targets are separated.")
    print("Late Python symbols are read through bounded streaming windows.")
    print("Ambiguous deletes and missing explicit targets fail closed.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
