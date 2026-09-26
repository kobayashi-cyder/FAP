#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer

import fap_v87_28_physics_solver_gateway as v28

base = v28.base
ROOT = Path(__file__).resolve().parent

MEDIA_PATHS = [
    ROOT / "releases" / "v87_13" / "media_generation",
    ROOT / "releases" / "v87_15" / "observed_media",
    ROOT / "releases" / "v87_16" / "media_portfolio",
    ROOT / "releases" / "v87_17" / "adaptive_fast_path",
    ROOT / "releases" / "v87_19" / "autonomous_media",
    ROOT / "releases" / "v87_20" / "media_lab",
    ROOT / "releases" / "v87_29" / "native_image",
    ROOT / "releases" / "v87_30" / "human_lbs",
    ROOT / "releases" / "v87_31" / "scene_image",
    ROOT / "releases" / "v87_32" / "photo_look",
    ROOT / "releases" / "v87_33" / "object_registry",
]
for path in reversed(MEDIA_PATHS):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")

from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_object_registry import ObjectRegistryManager, ObjectRegistryRuntime

VERSION = "87.33-unified-chat"


class FAPV8733Unified(v28.FAPV8728):
    """Current-mainline chat facade.

    Text/reasoning:
      V87.12 semantic/adaptive fast path -> V87.25..V87.28 structured/science/physics.
    Media:
      V87.33 object registry -> V87.32 photo-look renderer.
    """

    def __init__(self):
        super().__init__()
        media_runtime = base.RUNTIME / "media_v87_33"
        media_runtime.mkdir(parents=True, exist_ok=True)
        manager = ObjectRegistryManager(
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
        self.object_registry_runtime = ObjectRegistryRuntime(
            runtime_dir=media_runtime,
            manager=manager,
        )

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.33",
            "v87.33-object-registry",
            "v87.32-photo-look-native",
            "offline-native-image-generation",
            "scene-object-registry:human,dog,bird,cat,horse,car",
            "scene-graph-compliance-gate",
            "human-lbs",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self) -> dict:
        out = super().status()
        media = self.object_registry_runtime.status()
        skills = media.get("skills") or []
        first = skills[0] if skills else {}
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.33",
                "state": "ready",
                "chat_stack": {
                    "general_chat": "V87.12 semantic-adaptive fast path",
                    "structured_reasoning": "V87.25-V87.28",
                    "media": "V87.33 object-registry",
                    "renderer": "V87.32 photo-look-native",
                    "compatibility": "V87.28 and earlier text paths preserved",
                },
                "media_v87_33": {
                    "state": media.get("state"),
                    "offline": media.get("offline", True),
                    "fap_owned_engine": media.get("fap_owned_engine", True),
                    "supported_scene_objects": first.get(
                        "supported_scene_objects", []
                    ),
                    "render_style": first.get("render_style", ""),
                    "photo_look_capability": first.get(
                        "photo_look_capability", 0.0
                    ),
                    "learned_refiner": first.get("learned_refiner", False),
                    "photorealistic_verified": False,
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out

    def _latest_image_capability(self) -> dict:
        status = self.object_registry_runtime.status()
        skills = status.get("skills") or []
        engine = skills[0] if skills else {}
        objects = engine.get("supported_scene_objects") or []
        return {
            "ok": bool(skills),
            "reply": (
                "V87.33のFAPネイティブ画像生成器官を使用できます。"
                f"\nengine: {engine.get('engine_id', 'object-registry')}"
                f"\nobjects: {', '.join(map(str, objects))}"
                f"\nrender style: {engine.get('render_style', 'photo-look-native')}"
                f"\nphoto-look capability: {engine.get('photo_look_capability', 0.0)}"
                "\n外部画像APIは不要です。"
                "\nただし true photorealistic は未検証なので、"
                "「写真風」を必須条件にした場合はfail-closedで不合格になります。"
            ),
            "confidence": 0.99 if skills else 0.75,
        }

    def _latest_image_generate(self, text: str) -> dict:
        prompt = self.image.prompt_from(text).strip()
        if prompt.endswith("の"):
            prompt = prompt[:-1].rstrip()
        prompt = prompt or text.strip()

        constraints = []
        lowered = text.lower()
        if any(
            x in lowered
            for x in (
                "写真風",
                "フォトリアル",
                "photoreal",
                "photo-real",
                "photographic",
            )
        ):
            constraints.append("写真風")
        if "中央" in text or "center" in lowered:
            constraints.append("被写体を中央に保つ")

        try:
            generated = self.object_registry_runtime.generate(
                {
                    "prompt": prompt,
                    "media_type": "image",
                    "width": 768,
                    "height": 768,
                    "max_attempts": 2,
                    "constraints": constraints,
                }
            )
        except Exception as exc:
            return {
                "ok": False,
                "reply": "V87.33画像生成器官の実行に失敗しました: "
                + base.compact(exc),
                "confidence": 0.78,
                "artifacts": [],
            }

        artifact = generated.get("artifact") or {}
        issues = artifact.get("issues") or []
        issue_codes = [
            str(x.get("code", "")) for x in issues if x.get("code")
        ]
        artifacts = []
        url = str(artifact.get("url") or "")
        if url:
            artifacts.append(
                {
                    "type": "image",
                    "src": url,
                    "name": Path(url).name or "fap_v87_33.png",
                }
            )

        accepted = bool(generated.get("accepted"))
        if accepted:
            reply = (
                "V87.33のネイティブ画像生成で生成・検証に合格しました。"
                f"\nPrompt: {prompt}"
            )
        else:
            reply = (
                "V87.33のネイティブ画像生成で候補を生成しましたが、"
                "検証ゲートでは NOT ACCEPTED です。"
                f"\nPrompt: {prompt}"
            )
            if issue_codes:
                reply += "\nissues: " + ", ".join(issue_codes)

        return {
            "ok": accepted,
            "reply": reply,
            "confidence": (
                0.99
                if accepted
                else max(
                    0.58,
                    float(artifact.get("verification_score", 0.58)),
                )
            ),
            "artifacts": artifacts,
            "media_v87_33": generated,
        }

    def route(self, intent, text: str, history: list[dict]) -> dict:
        if intent.name == "image_capability":
            return self._latest_image_capability()
        if intent.name == "image_generate":
            return self._latest_image_generate(text)
        return super().route(intent, text, history)


CORE = FAPV8733Unified()
v28.CORE = CORE
v28.v27.CORE = CORE
v28.v27.v26.CORE = CORE
v28.v27.v26.v25.CORE = CORE
v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v28.Handler):
    server_version = "FAPV87.33UnifiedChat"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.33 UNIFIED CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("General chat: V87.12 semantic/adaptive fast path (preserved)")
    print("Structured reasoning: V87.25-V87.28 (preserved)")
    print("Image generation: V87.33 Object Registry + V87.32 photo-look")
    print("Objects: human, dog, bird, cat, horse, car")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
