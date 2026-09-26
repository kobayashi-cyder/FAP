#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer

import fap_v87_33_unified_chat_gateway as v33

base = v33.base
ROOT = Path(__file__).resolve().parent
V34_PATH = ROOT / "releases" / "v87_34" / "scene_graph2"
if str(V34_PATH) not in sys.path:
    sys.path.insert(0, str(V34_PATH))

from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_scene_graph2 import SceneGraph2Manager, SceneGraph2Runtime

VERSION = "87.34-unified-chat"


class FAPV8734Unified(v33.FAPV8733Unified):
    def __init__(self):
        super().__init__()
        runtime_dir = base.RUNTIME / "media_v87_34"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        manager = SceneGraph2Manager(
            artifact_dir=base.ARTIFACTS,
            observer_bindings={
                "image": (
                    ObserverBinding(
                        "actual_file_evidence",
                        ActualFileObserver(),
                        ("image",),
                    ),
                ),
            },
            integrity_critics={"image": (ArtifactIntegrityCritic(),)},
        )
        self.scene_graph2_runtime = SceneGraph2Runtime(
            runtime_dir=runtime_dir,
            manager=manager,
        )

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.34",
            "v87.34-scene-graph2",
            "scene-counts",
            "scene-attributes",
            "scene-relations",
            "scene-negative-constraints",
            "scene-viewpoint",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self) -> dict:
        out = super().status()
        media = self.scene_graph2_runtime.status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.34",
            "state": "ready",
            "chat_stack": {
                "general_chat": "V87.12 semantic-adaptive fast path",
                "structured_reasoning": "V87.25-V87.28",
                "media": "V87.34 Scene Graph 2",
                "renderer": "V87.32 photo-look-native",
                "object_registry": "V87.33",
            },
            "media_v87_34": media,
        })
        out["capabilities"] = self.capabilities()
        return out

    def _latest_image_capability(self) -> dict:
        s = self.scene_graph2_runtime.status()
        skill = (s.get("skills") or [{}])[0]
        return {
            "ok": True,
            "reply": (
                "V87.34 Scene Graph 2画像生成を使用できます。"
                "\n個数・色・状態・関係・除外条件・視点を構造化して検証します。"
                f"\nobjects: {', '.join(skill.get('supported_scene_objects', []))}"
                "\n写真風/イラスト指定は未達ならfail-closedで不合格にします。"
            ),
            "confidence": 0.99,
        }

    def _latest_image_generate(self, text: str) -> dict:
        prompt = self.image.prompt_from(text).strip()
        if prompt.endswith("の"):
            prompt = prompt[:-1].rstrip()
        prompt = prompt or text.strip()

        constraints = []
        lowered = text.lower()
        if any(x in lowered for x in ("写真風", "フォトリアル", "photoreal", "photographic")):
            constraints.append("写真風")
        if any(x in lowered for x in ("イラスト", "アニメ", "illustration", "anime", "cartoon")):
            constraints.append("イラスト")
        if "中央" in text or "center" in lowered:
            constraints.append("被写体を中央に保つ")

        try:
            generated = self.scene_graph2_runtime.generate({
                "prompt": prompt,
                "media_type": "image",
                "width": 768,
                "height": 768,
                "max_attempts": 2,
                "constraints": constraints,
            })
        except Exception as exc:
            return {
                "ok": False,
                "reply": "V87.34画像生成器官の実行に失敗しました: " + base.compact(exc),
                "confidence": 0.78,
                "artifacts": [],
            }

        artifact = generated.get("artifact") or {}
        issues = artifact.get("issues") or []
        issue_codes = [str(x.get("code", "")) for x in issues if x.get("code")]
        artifacts = []
        url = str(artifact.get("url") or "")
        if url:
            artifacts.append({
                "type": "image",
                "src": url,
                "name": Path(url).name or "fap_v87_34.png",
            })

        accepted = bool(generated.get("accepted"))
        reply = (
            "V87.34 Scene Graph 2で生成・検証に合格しました。"
            if accepted
            else "V87.34 Scene Graph 2で候補を生成しましたが、検証ゲートでは NOT ACCEPTED です。"
        )
        reply += f"\nPrompt: {prompt}"
        if issue_codes:
            reply += "\nissues: " + ", ".join(issue_codes)

        return {
            "ok": accepted,
            "reply": reply,
            "confidence": 0.99 if accepted else max(0.58, float(artifact.get("verification_score", 0.0))),
            "artifacts": artifacts,
            "media_v87_34": generated,
        }


CORE = FAPV8734Unified()
v33.CORE = CORE
v33.v28.CORE = CORE
v33.v28.v27.CORE = CORE
v33.v28.v27.v26.CORE = CORE
v33.v28.v27.v26.v25.CORE = CORE
v33.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v33.Handler):
    server_version = "FAPV87.34UnifiedChat"


def main():
    print("FAP V87.34 UNIFIED CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Image generation: V87.34 Scene Graph 2")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
