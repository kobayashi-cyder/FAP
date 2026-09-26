#!/usr/bin/env python3
from __future__ import annotations

import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_62_semantic_action_gateway as v62

base = v62.base
VERSION = "87.63-unified-chat"


class FAPV8763Unified(v62.FAPV8762Unified):
    """V87.62 plus self-contained local raster image generation."""

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.63",
            "self-contained-local-raster-image-generation",
            "declarative-visual-concepts",
            "stdlib-png-renderer",
            "external-image-api-optional",
            "structural-image-verification",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        local_ok, local_status = self.image.orchestrator.local.available()
        external_ok, external_status = self.image.orchestrator._external_available()
        out.update({
            "version": VERSION,
            "mainline_version": "87.63",
            "local_image_backend": {
                "enabled": True,
                "available": local_ok,
                "status": local_status,
                "concepts": len(self.image.orchestrator.local.knowledge.concepts),
                "external_backend_available": external_ok,
                "external_backend_status": external_status,
                "network_required": False,
                "third_party_python_packages_required": False,
                "output": "PNG",
                "quality_class": "lightweight illustration",
            },
        })
        out["capabilities"] = self.capabilities()
        return out


CORE = FAPV8763Unified()
v62.CORE = CORE
v62.v61.CORE = CORE
v62.v61.v60.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v62.Handler):
    server_version = "FAPV87.63LocalRaster"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.63",
                "state": "ready",
            })
            return
        super().do_GET()


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.63 SELF-CONTAINED LOCAL RASTER")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Image fallback: semantic action -> declarative visual concept -> local scene graph -> PNG")
    print("External image API: optional")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
