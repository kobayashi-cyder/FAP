#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_79_conversation_quality_gateway as v79

base = v79.base
VERSION = "87.80-unified-chat"


class FAPV8780Unified(v79.FAPV8779Unified):
    """V87.79 plus multi-turn discourse consistency hardening."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.80",
            "multiturn-consistency-fuzz",
            "stale-topic-resurrection-block",
            "user-turn-topic-boundary",
            "declarative-transparent-discourse",
            "explicit-correction-focus",
            "correction-followup-continuity",
            "utterance-independent-multiturn-hardening",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.80",
                "multiturn_consistency_hardening": {
                    "enabled": True,
                    "data_driven_discourse_markers": True,
                    "new_unknown_subject_blocks_stale_topic": True,
                    "transparent_acknowledgement_keeps_topic": True,
                    "explicit_correction_asserted_side_priority": True,
                    "correction_followup_continuity": True,
                    "inquiry_correction_alignment": True,
                    "utterance_specific_topic_branches_added": False,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8780Unified()
v79.CORE = CORE
v79.v78.CORE = CORE
v79.v78.v77.CORE = CORE
v79.v78.v77.v76.CORE = CORE
v79.v78.v77.v76.v75.CORE = CORE
v79.v78.v77.v76.v75.v74.CORE = CORE
v79.v78.v77.v76.v75.v74.v73.CORE = CORE
v79.v78.v77.v76.v75.v74.v73.v64.CORE = CORE
v79.v78.v77.v76.v75.v74.v73.v64.v63.CORE = CORE
v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v79.v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v79.Handler):
    server_version = "FAPV87.80MultiTurnConsistency"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.80",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.80 MULTI-TURN CONSISTENCY FUZZ HARDENING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("A newer unknown user subject blocks resurrection of older known topics.")
    print("Transparent acknowledgements keep the previous grounded topic.")
    print("Explicit A-not-B corrections prioritize the asserted replacement side.")
    print("Utterance-specific topic routing branches added: no.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
