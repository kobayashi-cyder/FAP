#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_63_local_raster_gateway as v63

base = v63.base
VERSION = "87.64-unified-chat"


class FAPV8764Unified(v63.FAPV8763Unified):
    """V87.63 plus honest quality gating and multi-concept composition."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.64",
            "multi-concept-local-composition",
            "schematic-draft-quality-gate",
            "requested-concept-coverage",
            "no-false-ok-for-low-quality-raster",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.64",
            "local_image_quality": {
                "multi_concept": True,
                "quality_gate": True,
                "schematic_drafts_are_final_only_when_requested": True,
                "default_quality_class": "schematic-draft",
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8764Unified()
v63.CORE = CORE
v63.v62.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v63.Handler):
    server_version = "FAPV87.64RasterQuality"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.64",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.64 MULTI-CONCEPT RASTER + QUALITY GATE")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Schematic raster is no longer certified as finished general image generation.")
    print("Multiple matched visual concepts are composed generically.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
