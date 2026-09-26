#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_80_multiturn_consistency_gateway as v80

base = v80.base
VERSION = "87.81-unified-chat"


class FAPV8781Unified(v80.FAPV8780Unified):
    """V87.80 plus consolidated coding and coding-conversation continuity."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.81",
            "structured-multi-edit-repository-coding",
            "mixed-operation-repository-planning",
            "automatic-repository-test-selection",
            "content-free-repository-session-continuity",
            "multi-turn-coding-followup-path-affinity",
            "coding-collaboration-handoff",
            "side-branch-capability-consolidation",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.81",
                "coding_conversation": {
                    "enabled": True,
                    "structured_multi_edit": True,
                    "mixed_operation_planning": True,
                    "automatic_test_selection_available": True,
                    "repository_session_continuity": True,
                    "repository_session_stores_source_text": False,
                    "followup_path_affinity": True,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8781Unified()
v80.CORE = CORE
v80.v79.CORE = CORE
v80.v79.v78.CORE = CORE
v80.v79.v78.v77.CORE = CORE
v80.v79.v78.v77.v76.CORE = CORE
v80.v79.v78.v77.v76.v75.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v80.v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v80.Handler):
    server_version = "FAPV87.81CodingConversation"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.81",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.81 CODING + CONVERSATION CONSOLIDATION")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Structured repository coding is consolidated into the mainline.")
    print("Short coding follow-ups may reuse bounded prior repository paths.")
    print("Repository continuity stores hashes/path metadata only, never source text.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
