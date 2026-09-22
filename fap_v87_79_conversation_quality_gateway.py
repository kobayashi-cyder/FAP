#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_78_conversation_fuzz_gateway as v78

base = v78.base
VERSION = "87.79-unified-chat"


class FAPV8779Unified(v78.FAPV8778Unified):
    """V87.78 plus semantic conversation-quality fuzz hardening."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.79",
            "conversation-quality-fuzz",
            "subject-sensitive-context-reference",
            "user-topic-priority",
            "unicode-separator-normalization",
            "context-only-inquiry-deferral",
            "semantic-route-stability",
            "utterance-independent-quality-hardening",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.79",
                "conversation_quality_hardening": {
                    "enabled": True,
                    "data_driven_quality_corpus": True,
                    "explicit_subject_history_hijack_blocked": True,
                    "context_only_followup_preserved": True,
                    "user_stated_topic_priority": True,
                    "unicode_separator_normalization": True,
                    "context_only_mass_inquiry_deferred": True,
                    "utterance_specific_branches_added": False,
                    "fca_required": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8779Unified()
v78.CORE = CORE
v78.v77.CORE = CORE
v78.v77.v76.CORE = CORE
v78.v77.v76.v75.CORE = CORE
v78.v77.v76.v75.v74.CORE = CORE
v78.v77.v76.v75.v74.v73.CORE = CORE
v78.v77.v76.v75.v74.v73.v64.CORE = CORE
v78.v77.v76.v75.v74.v73.v64.v63.CORE = CORE
v78.v77.v76.v75.v74.v73.v64.v63.v62.CORE = CORE
v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.CORE = CORE
v78.v77.v76.v75.v74.v73.v64.v63.v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v78.Handler):
    server_version = "FAPV87.79ConversationQuality"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json(
                {
                    "version": VERSION,
                    "mainline_version": "87.79",
                    "state": "ready",
                }
            )
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.79 CONVERSATION QUALITY FUZZ HARDENING")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Explicit current subjects cannot be replaced by prior conversation topics.")
    print("Subjectless clarification keeps the user-stated recent topic.")
    print("Unicode and punctuation variants are normalized for semantic matching.")
    print("Utterance-specific routing branches added: no.")
    print("FCA: optional, not required.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
