#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_45_inquiry_loop_gateway as v45

base = v45.base
VERSION = "87.46-unified-chat"


class FAPV8746Unified(v45.FAPV8745Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.46",
            "mass-inquiry:96-default",
            "answer-to-question-expansion",
            "iterative-question-resolution",
            "configurable-inquiry-count:256-max",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.46",
            "mass_inquiry": {
                "default_target": getattr(self.inquiry, "default_target", 96),
                "max_target": 256,
                "max_rounds": getattr(self.inquiry, "max_rounds", 5),
                "answer_to_question_expansion": True,
                "topic_specific_routing": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8746Unified()
v45.CORE = CORE
v45.v44.CORE = CORE
v45.v44.v43.CORE = CORE
v45.v44.v43.v42.CORE = CORE
v45.v44.v43.v42.v41.CORE = CORE
v45.v44.v43.v42.v41.v40.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v45.Handler):
    server_version = "FAPV87.46MassInquiry"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.46",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.46 MASS INQUIRY")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Default inquiry target: 96 questions; explicit requests can raise it to 256.")
    print("Flow: retrieve -> mass question grid -> resolve -> answer-derived expansion -> retry.")
    print("Knowledge growth remains data-driven; no topic-specific router growth.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
