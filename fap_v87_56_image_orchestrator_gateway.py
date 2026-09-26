#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_55_recursive_research_gateway as v55

base = v55.base
VERSION = "87.56-unified-chat"


class FAPV8756Unified(v55.FAPV8755Unified):
    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.56",
            "image-request-spec",
            "multi-candidate-image-generation",
            "image-self-critique",
            "image-repair-loop",
            "optional-clip-interrogate",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        ok, detail = self.image.available()
        out.update({
            "version": VERSION,
            "mainline_version": "87.56",
            "image_orchestrator": {
                "enabled": True,
                "generator_connected": ok,
                "generator_status": detail,
                "candidate_count": self.image.orchestrator.candidates,
                "round_budget": self.image.orchestrator.rounds,
                "clip_interrogate_optional": True,
                "automatic_repair": True,
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8756Unified()
v55.CORE = CORE
v55.v54.CORE = CORE
v55.v54.v53.CORE = CORE
v55.v54.v53.v52.CORE = CORE
v55.v54.v53.v52.v51.CORE = CORE
v55.v54.v53.v52.v51.v50.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.CORE = CORE
v55.v54.v53.v52.v51.v50.v49.v48.v47.v46.v45.v44.v43.v42.v41.v40.v39.v38.v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v55.Handler):
    server_version = "FAPV87.56ImageOrchestrator"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.56",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.56 IMAGE ORCHESTRATOR")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Image flow: request spec -> candidates -> optional CLIP critique -> repair -> best selection")
    print("Photorealistic quality depends on the connected local image model.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
