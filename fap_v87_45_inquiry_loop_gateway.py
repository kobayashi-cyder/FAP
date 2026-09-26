#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_44_context_followup_gateway as v44

base = v44.base
VERSION = "87.45-unified-chat"


class FAPV8745Unified(v44.FAPV8744Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.45",
            "generic-inquiry-loop",
            "question-generation",
            "question-resolution",
            "retrieval-grounded-inquiry",
            "data-driven-domain-growth",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.45",
            "inquiry_engine": {
                "generic": True,
                "retrieve": True,
                "generate_questions": True,
                "resolve_questions": True,
                "retry_unresolved": True,
                "knowledge_as_data": True,
                "topic_specific_routing_growth": False,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8745Unified()
v44.CORE = CORE
v44.v43.CORE = CORE
v44.v43.v42.CORE = CORE
v44.v43.v42.v41.CORE = CORE
v44.v43.v42.v41.v40.CORE = CORE
v44.v43.v42.v41.v40.v39.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v44.Handler):
    server_version = "FAPV87.45InquiryLoop"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.45",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.45 GENERIC INQUIRY LOOP")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Flow: retrieve -> generate questions -> answer from evidence -> retry unresolved -> synthesize.")
    print("Knowledge grows as data under knowledge/, not as topic-specific router branches.")
    print("V87.44 context follow-up and prior stacks are preserved as fallback.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
