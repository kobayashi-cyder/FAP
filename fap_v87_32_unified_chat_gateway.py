#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer

import fap_v87_28_physics_solver_gateway as v28

base = v28.base
ROOT = Path(__file__).resolve().parent

# Reuse the verified V87.32 media stack inside the current chat gateway.
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
from fap_photo_look import PhotoLookManager, PhotoLookMediaLabRuntime

VERSION = "87.32-unified-chat"


class FAPV8732Unified(v28.FAPV8728):
    """Latest mainline chat facade.

    Text/reasoning keeps the V87.28 -> V87.12 compatible chain.
    Image generation/capability is upgraded to the V87.32 native photo-look path.
    """

    def __init__(self):
        super().__init__()
        media_runtime = base.RUNTIME / "media_v87_32"
        media_runtime.mkdir(parents=True, exist_ok=True)
        manager = PhotoLookManager(
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
        self.photo_runtime = PhotoLookMediaLabRuntime(
            runtime_dir=media_runtime,
            manager=manager,
        )

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        extras = [
            "latest-mainline-chat:v87.32",
            "v87.32-photo-look-native",
            "offline-native-image-generation",
            "scene-graph-compliance-gate",
            "human-lbs",
            "photo-look-quality-critic",
        ]
        for item in extras:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self) -> dict:
        out = super().status()
        media = self.photo_runtime.status()
        out.update(
            {
                "version": VERSION,
                "mainline_version": "87.32",
                "state": "ready",
                "chat_stack": {
                    "general_chat": "V87.12 semantic-adaptive fast path",
                    "structured_reasoning": "V87.25-V87.28",
                    "media": "V87.32 photo-look-native",
                    "compatibility": "V87.28 and earlier preserved",
                },
                "media_v87_32": {
                    "state": media.get("state"),
                    "offline": media.get("offline", True),
                    "fap_owned_engine": media.get("fap_owned_engine", True),
                    "photorealistic_verified": (
                        (media.get("verification") or {}).get(
                            "photorealistic_verified", False
                        )
                    ),
                    "skills": media.get("skills", []),
                },
            }
        )
        out["capabilities"] = self.capabilities()
        return out

    def _latest_image_capability(self) -> dict:
        status = self.photo_runtime.status()
        skills = status.get("skills") or []
        engine = skills[0] if skills else {}
        capability = engine.get("photo_look_capability", 0.0)
        return {
            "ok": bool(skills),
            "reply": (
                "V87.32のFAPネイティブ画像生成器官を使用できます。"
                f"\nengine: {engine.get('engine_id', 'photo-look-native')}"
                f"\nphoto-look capability: {capability}"
                "\n外部画像APIは不要です。"
                "\nただし true photorealistic は未検証なので、"
                "「写真風」のハード条件はfail-closedで不合格になる場合があります。"
            ),
            "confidence": 0.99 if skills else 0.75,
        }

    def _latest_image_generate(self, text: str) -> dict:
        prompt = self.image.prompt_from(text)
        constraints = []
        if any(x in text for x in ("写真風", "フォトリアル", "photoreal", "photo-real")):
            constraints.append("写真風")
        if "中央" in text or "center" in text.lower():
            constraints.append("被写体を中央に保つ")

        try:
            generated = self.photo_runtime.generate(
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
                "reply": "V87.32画像生成器官の実行に失敗しました: " + base.compact(exc),
                "confidence": 0.78,
                "artifacts": [],
            }

        artifact = generated.get("artifact") or {}
        issues = artifact.get("issues") or []
        issue_codes = [str(x.get("code", "")) for x in issues if x.get("code")]
        artifacts = []
        if artifact.get("url"):
            artifacts.append(
                {
                    "type": "image",
                    "src": artifact["url"],
                    "name": artifact.get("filename", "fap_v87_32.png"),
                }
            )

        accepted = bool(generated.get("accepted"))
        if accepted:
            reply = (
                "V87.32のネイティブ画像生成で生成・検証に合格しました。"
                f"\nPrompt: {prompt}"
            )
        else:
            reply = (
                "V87.32のネイティブ画像生成で候補を生成しましたが、"
                "検証ゲートでは NOT ACCEPTED です。"
                f"\nPrompt: {prompt}"
            )
            if issue_codes:
                reply += "\nissues: " + ", ".join(issue_codes)

        return {
            "ok": accepted,
            "reply": reply,
            "confidence": (
                0.99 if accepted else max(0.58, float(artifact.get("verification_score", 0.58)))
            ),
            "artifacts": artifacts,
            "media_v87_32": generated,
        }

    def route(self, intent, text: str, history: list[dict]) -> dict:
        if intent.name == "image_capability":
            return self._latest_image_capability()
        if intent.name == "image_generate":
            return self._latest_image_generate(text)
        return super().route(intent, text, history)


CORE = FAPV8732Unified()
v28.CORE = CORE
v28.v27.CORE = CORE
v28.v27.v26.CORE = CORE
v28.v27.v26.v25.CORE = CORE
v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v28.Handler):
    server_version = "FAPV87.32UnifiedChat"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.32 UNIFIED CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("General chat: V87.12 semantic/adaptive fast path (preserved)")
    print("Structured reasoning: V87.25-V87.28 (preserved)")
    print("Image generation: V87.32 native photo-look")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
