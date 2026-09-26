#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
from http.server import ThreadingHTTPServer

import fap_v87_37_sparse_unified_chat_gateway as v37

base = v37.base
ROOT = Path(__file__).resolve().parent
NATIVE_PATH = ROOT / "releases" / "v87_38" / "native_raster"
if str(NATIVE_PATH) not in sys.path:
    sys.path.insert(0, str(NATIVE_PATH))

VERSION = "87.38-unified-chat"


class FAPV8738Unified(v37.FAPV8737Unified):
    def _activate_native(self, target: str):
        from fap_native_raster import activate_native_renderers
        return activate_native_renderers((target,))

    def _build_scene_organ(self):
        organ = super()._build_scene_organ()
        self._activate_native("scene_graph2")
        return organ

    def _build_cat_organ(self):
        organ = super()._build_cat_organ()
        self._activate_native("morphology")
        return organ

    def _build_dna_organ(self):
        organ = super()._build_dna_organ()
        self._activate_native("scientific_dna")
        return organ

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.38",
            "native-c99-raster-core",
            "native-z-buffer",
            "native-material-shading",
            "native-sparse-fxaa",
            "native-subject-filmic",
            "ctypes-portable-bridge",
            "python-fallback-preserved",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        from fap_native_raster import native_status
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.38",
            "native_raster": native_status(),
        })
        out["chat_stack"] = {
            **dict(out.get("chat_stack", {})),
            "renderer": "V87.38 C99 native raster with V87.37 fallback",
        }
        out["capabilities"] = self.capabilities()
        return out

    def _latest_image_capability(self):
        from fap_native_raster import native_status
        s = native_status()
        backend = (
            f"native {s.get('version')}"
            if s.get("available")
            else "V87.37 Python fallback"
        )
        return {
            "ok": True,
            "reply": (
                "V87.38 Native Raster Coreを使用できます。"
                "\ntriangle raster / z-buffer / material shading / sparse FXAA / "
                "subject filmicをC99へ移しました。"
                f"\nactive backend: {backend}"
                "\n器官選択とLazy LoadはV87.37の疎実行を維持します。"
            ),
            "confidence": 0.99,
        }


CORE = FAPV8738Unified()
v37.CORE = CORE
v37.v28.CORE = CORE
v37.v28.v27.CORE = CORE
v37.v28.v27.v26.CORE = CORE
v37.v28.v27.v26.v25.CORE = CORE
v37.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v37.Handler):
    server_version = "FAPV87.38Native"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    from fap_native_raster import native_status
    print("FAP V87.38 NATIVE RASTER")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print(f"Native raster: {native_status()}")
    print("Sparse routing/lazy organs: V87.37 preserved")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
