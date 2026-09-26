#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import urllib.parse
from http.server import ThreadingHTTPServer

import fap_v87_38_native_unified_chat_gateway as v38

base=v38.base
ROOT=Path(__file__).resolve().parent
P=ROOT/"releases"/"v87_39"/"native_geometry"
if str(P) not in sys.path:
    sys.path.insert(0,str(P))

VERSION="87.39-unified-chat"

class FAPV8739Unified(v38.FAPV8738Unified):
    def _activate_geometry(self,*targets):
        from fap_native_geometry import activate_native_geometry
        return activate_native_geometry(targets)

    def _build_scene_organ(self):
        organ=super()._build_scene_organ()
        self._activate_geometry("scene_graph2","human_lbs")
        return organ

    def _build_cat_organ(self):
        organ=super()._build_cat_organ()
        self._activate_geometry("morphology")
        return organ

    def _build_dna_organ(self):
        organ=super()._build_dna_organ()
        self._activate_geometry("scientific_dna")
        return organ

    def capabilities(self):
        caps=super().capabilities()
        for item in [
            "latest-mainline-chat:v87.39",
            "native-projection",
            "native-normal-accumulation",
            "native-active-tile-discovery",
            "native-cat-coat-patterns",
            "native-sparse-lbs",
            "affected-vertex-lbs",
        ]:
            if item not in caps: caps.append(item)
        return caps

    def status(self):
        from fap_native_geometry import native_geometry_status,last_lbs_stats
        out=super().status()
        out.update({
            "version":VERSION,
            "mainline_version":"87.39",
            "native_geometry":native_geometry_status(),
            "last_lbs":last_lbs_stats(),
        })
        out["chat_stack"]={
            **dict(out.get("chat_stack",{})),
            "geometry":"V87.39 C99 projection/normals/tiles/coat/LBS",
            "renderer":"V87.38 C99 raster fed by V87.39 native geometry",
        }
        out["capabilities"]=self.capabilities()
        return out

    def _latest_image_capability(self):
        from fap_native_geometry import native_geometry_status
        s=native_geometry_status()
        state=f"native {s.get('version')}" if s.get("available") else "V87.38/V87.37 fallback"
        return {
            "ok":True,
            "reply":(
                "V87.39 Native Geometry Coreを使用できます。"
                "\nprojection / normal accumulation / active-tile discovery / "
                "猫coat pattern / sparse LBSをC99へ移しました。"
                f"\nactive geometry backend: {state}"
                "\nV87.38 Native RasterとV87.37 SparseRouterは維持します。"
            ),
            "confidence":0.99,
        }

CORE=FAPV8739Unified()
v38.CORE=CORE
v38.v37.CORE=CORE
v38.v37.v28.CORE=CORE
v38.v37.v28.v27.CORE=CORE
v38.v37.v28.v27.v26.CORE=CORE
v38.v37.v28.v27.v26.v25.CORE=CORE
v38.v37.v28.v27.v26.v25.v12.CORE=CORE
base.CORE=CORE
base.VERSION=VERSION

class Handler(v38.Handler):
    server_version="FAPV87.39NativeGeometry"

    def do_GET(self):
        # Startup/readiness probes must not build the full recursive status
        # payload. On Windows the old 1-second /api/v1/status probe could abort
        # the socket while CORE.status() was still serializing, creating
        # WinError 10053 and making a healthy server look unready.
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/v1/ready":
            self.send_json({
                "version": VERSION,
                "mainline_version": "87.39",
                "state": "ready",
            })
            return
        super().do_GET()

def main():
    from fap_native_geometry import native_geometry_status
    print("FAP V87.39 NATIVE GEOMETRY")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print(f"Native geometry: {native_geometry_status()}")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST,base.PORT),Handler).serve_forever()

if __name__=="__main__":
    main()
