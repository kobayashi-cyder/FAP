#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_46_mass_inquiry_gateway as v46

base = v46.base
VERSION = "87.47-unified-chat"


class FAPV8747Unified(v46.FAPV8746Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.47",
            "mass-inquiry:256-default",
            "mass-inquiry:2048-burst",
            "iterative-question-resolution:8-rounds",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.47",
            "mass_inquiry": {
                "default_target": getattr(self.inquiry, "default_target", 256),
                "burst_target": 2048,
                "max_target": 2048,
                "max_rounds": getattr(self.inquiry, "max_rounds", 8),
                "answer_to_question_expansion": True,
                "topic_specific_routing": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8747Unified()
v46.CORE = CORE
v46.v45.CORE = CORE
v46.v45.v44.CORE = CORE
v46.v45.v44.v43.CORE = CORE
v46.v45.v44.v43.v42.CORE = CORE
v46.v45.v44.v43.v42.v41.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v46.Handler):
    server_version = "FAPV87.47MassInquiryBurst"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.47",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.47 MASS INQUIRY BURST")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Default inquiry target: 256 questions.")
    print("Burst phrases such as とにかく増やして / 最大限 / 限界まで request 2048 questions.")
    print("Resolution retry budget: up to 8 rounds.")
    print("Knowledge growth remains data-driven; no topic-specific router growth.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
