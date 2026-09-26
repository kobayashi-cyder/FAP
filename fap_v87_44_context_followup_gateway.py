#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_43_reflective_chat_gateway as v43

base = v43.base
VERSION = "87.44-unified-chat"


class FAPV8744Unified(v43.FAPV8743Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.44",
            "natural-context-followup",
            "clarification-from-recent-topic",
            "plain-language-reexplanation",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.44",
            "context_followup": {
                "natural_clarification": True,
                "recent_topic_resolution": True,
                "plain_language_reexplanation": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8744Unified()
v43.CORE = CORE
v43.v42.CORE = CORE
v43.v42.v41.CORE = CORE
v43.v42.v41.v40.CORE = CORE
v43.v42.v41.v40.v39.CORE = CORE
v43.v42.v41.v40.v39.v38.CORE = CORE
v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v43.Handler):
    server_version = "FAPV87.44ContextFollowup"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.44",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.44 NATURAL CONTEXT FOLLOW-UP")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Natural clarification questions resolve the recent topic and can re-explain it plainly.")
    print("V87.43 reflective chat and all prior factual/science/media stacks are preserved.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
