#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer

import fap_v87_34_unified_chat_gateway as v34

base = v34.base
ROOT = Path(__file__).resolve().parent
for p in (
    ROOT / "releases" / "v87_35" / "morphology",
    ROOT / "releases" / "v87_36" / "scientific_geometry",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
from fap_observed_media import ObserverBinding
from fap_morphology import MorphologyManager
from fap_scientific_geometry import ScientificGeometryManager, ScientificGeometryRuntime

VERSION = "87.36-unified-chat"


class FAPV8736Unified(v34.FAPV8734Unified):
    def __init__(self):
        super().__init__()
        common_observers = {
            "image": (
                ObserverBinding("actual_file_evidence", ActualFileObserver(), ("image",)),
            )
        }
        common_critics = {"image": (ArtifactIntegrityCritic(),)}
        self.morphology_manager = MorphologyManager(
            artifact_dir=base.ARTIFACTS,
            observer_bindings=common_observers,
            integrity_critics=common_critics,
        )
        scientific_manager = ScientificGeometryManager(
            artifact_dir=base.ARTIFACTS,
            observer_bindings=common_observers,
            integrity_critics=common_critics,
        )
        self.scientific_runtime = ScientificGeometryRuntime(
            runtime_dir=base.RUNTIME / "media_v87_36",
            manager=scientific_manager,
        )

    def capabilities(self) -> list[str]:
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.36",
            "v87.35-cat-morphology",
            "cat-calico",
            "cat-hachiware",
            "cat-tabby-patterns",
            "v87.36-scientific-geometry",
            "scientific-dna",
            "verified-b-dna",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self) -> dict:
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.36",
            "state": "ready",
            "chat_stack": {
                **dict(out.get("chat_stack", {})),
                "morphology": "V87.35 cat coat/face patterns",
                "scientific_geometry": "V87.36 verified B-DNA",
            },
            "scientific_v87_36": self.scientific_runtime.status(),
            "morphology_v87_35": self.morphology_manager.status(),
        })
        out["capabilities"] = self.capabilities()
        return out

    @staticmethod
    def _is_dna_request(text: str) -> bool:
        return bool(re.search(
            r"DNA|デオキシリボ核酸|B[- ]?DNA|A[- ]?DNA|Z[- ]?DNA|塩基対",
            text,
            re.I,
        ))

    @staticmethod
    def _is_cat_pattern_request(text: str) -> bool:
        return bool(re.search(
            r"三毛|八割れ|ハチワレ|キジトラ|サバトラ|茶トラ|サビ|calico|hachiware|tabby|tortoiseshell",
            text,
            re.I,
        ))

    def _latest_image_capability(self) -> dict:
        base_cap = super()._latest_image_capability()
        base_cap["reply"] += (
            "\nV87.35: 三毛・八割れ・トラ柄・サビ猫。"
            "\nV87.36: パラメトリックB-DNA（塩基対数・配列・相補性・らせん物理値を検証）。"
        )
        return base_cap

    def _scientific_generate(self, text: str) -> dict:
        prompt = self.image.prompt_from(text).strip() or text.strip()
        try:
            generated = self.scientific_runtime.generate({
                "prompt": prompt,
                "media_type": "image",
                "width": 768,
                "height": 768,
                "max_attempts": 1,
                "constraints": [],
            })
        except Exception as exc:
            return {
                "ok": False,
                "reply": "V87.36 DNA生成器官の実行に失敗しました: " + base.compact(exc),
                "confidence": 0.78,
                "artifacts": [],
            }
        a = generated.get("artifact") or {}
        artifacts = []
        if a.get("url"):
            artifacts.append({"type": "image", "src": a["url"], "name": Path(a["url"]).name})
        accepted = bool(generated.get("accepted"))
        geometry = a.get("geometry") or {}
        issues = [x.get("code") for x in a.get("issues", []) if x.get("code")]
        reply = (
            "V87.36 Scientific GeometryでDNAを生成・科学検証しました。"
            if accepted
            else "V87.36でDNA候補を生成しましたが、科学検証はNOT ACCEPTEDです。"
        )
        if geometry:
            reply += (
                f"\nform={geometry.get('form')} bp={geometry.get('base_pairs')} "
                f"handedness={geometry.get('handedness')} pitch={geometry.get('pitch_nm')}nm"
            )
        if issues:
            reply += "\nissues: " + ", ".join(issues)
        return {
            "ok": accepted,
            "reply": reply,
            "confidence": 0.99 if accepted else 0.70,
            "artifacts": artifacts,
            "scientific_v87_36": generated,
        }

    def _morphology_generate(self, text: str) -> dict:
        prompt = self.image.prompt_from(text).strip() or text.strip()
        req = GenerationRequest(
            prompt=prompt,
            media_type="image",
            width=768,
            height=768,
            max_attempts=1,
            min_score=0.99,
            constraints=(),
        )
        try:
            run = self.morphology_manager.generate(req)
        except Exception as exc:
            return {
                "ok": False,
                "reply": "V87.35猫Morphologyの実行に失敗しました: " + base.compact(exc),
                "confidence": 0.78,
                "artifacts": [],
            }
        result = run.result
        candidate = result.best_candidate
        if candidate is None:
            return {"ok": False, "reply": "猫パターン候補を生成できませんでした。", "confidence": 0.5, "artifacts": []}
        artifact = candidate.artifact
        url = "/artifacts/" + Path(artifact.locator).name
        cats = artifact.metadata.get("morphology", {}).get("cat_patterns", [])
        return {
            "ok": bool(result.accepted),
            "reply": (
                "V87.35 Morphologyで猫の毛柄・顔模様を生成しました。"
                f"\npatterns={cats}"
            ),
            "confidence": 0.99 if result.accepted else 0.75,
            "artifacts": [{"type": "image", "src": url, "name": Path(url).name}],
            "morphology_v87_35": {
                "accepted": bool(result.accepted),
                "patterns": cats,
                "score": float(candidate.critique.score),
            },
        }

    def _latest_image_generate(self, text: str) -> dict:
        if self._is_dna_request(text):
            return self._scientific_generate(text)
        if self._is_cat_pattern_request(text):
            return self._morphology_generate(text)
        return super()._latest_image_generate(text)


CORE = FAPV8736Unified()
v34.CORE = CORE
v34.v33.CORE = CORE
v34.v33.v28.CORE = CORE
v34.v33.v28.v27.CORE = CORE
v34.v33.v28.v27.v26.CORE = CORE
v34.v33.v28.v27.v26.v25.CORE = CORE
v34.v33.v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v34.Handler):
    server_version = "FAPV87.36UnifiedChat"


def main():
    print("FAP V87.36 UNIFIED CHAT")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Cat patterns: V87.35")
    print("Scientific DNA: V87.36")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
