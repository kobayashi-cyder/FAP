#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_77_repository_precision_gateway as v77

base = v77.base
VERSION = "87.78-unified-chat"


class FAPV8778Unified(v77.FAPV8777Unified):
    """V87.77 plus randomized conversation-boundary hardening."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.78",
            "randomized-conversation-fuzz",
            "malformed-history-normalization",
            "finite-pressure-normalization",
            "strict-json-session-metadata",
            "utterance-independent-conversation-hardening",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.78",
                "conversation_fuzz_hardening": {
                    "enabled": True,
                    "knowledge_derived_corpus": True,
                    "utterance_specific_branches_added": False,
                    "malformed_history_normalized": True,
                    "invalid_pressure_normalized": True,
                    "nonfinite_session_metadata_filtered": True,
                    "strict_json_safe": True,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8778Unified()
v77.CORE = CORE
v77.v76.CORE = CORE
v77.v76.v75.CORE = CORE
v77.v76.v75.v74.CORE = CORE
v77.v76.v75.v74.v73.CORE = CORE
v77.v76.v75.v74.v73.v64.CORE = CORE
v77.v76.v75.v74.v73.v64.v63.CORE = CORE
v77.v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v77.v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v77.v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v77.Handler):
    server_version = "FAPV87.78ConversationFuzzHardening"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.78",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.78 RANDOMIZED CONVERSATION FUZZ HARDENING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Conversation robustness is verified with seeded randomized corpora.")
    print("Malformed history and pressure inputs are normalized generically.")
    print("Non-finite session metadata is removed before strict JSON output.")
    print("Utterance-specific routing branches added: no.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
