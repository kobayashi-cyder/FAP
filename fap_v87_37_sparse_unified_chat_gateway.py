#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from http.server import ThreadingHTTPServer

import fap_v87_28_physics_solver_gateway as v28

base = v28.base
ROOT = Path(__file__).resolve().parent
VERSION = "87.37-unified-chat"

# Path registration is cheap. Media modules themselves remain unloaded until a
# sparse route activates the corresponding organ.
PATHS = [
    ROOT / "releases" / "v82" / "adaptive_circuits",
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
    ROOT / "releases" / "v87_34" / "scene_graph2",
    ROOT / "releases" / "v87_35" / "morphology",
    ROOT / "releases" / "v87_36" / "scientific_geometry",
    ROOT / "releases" / "v87_37" / "sparse_execution",
]
for path in reversed(PATHS):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from fap_sparse_execution.routing import LazyOrganPool, SparseOrganRouter


class FAPV8737Unified(v28.FAPV8728):
    """Sparse end-to-end current-mainline facade.

    General chat and reasoning stay on the established V87.28-and-earlier text
    stack. Media organs are verifier-first routed and loaded only when selected.
    """

    def __init__(self):
        super().__init__()
        self.organ_router = SparseOrganRouter()
        self.organ_pool = LazyOrganPool()
        self.organ_pool.register("scene", self._build_scene_organ)
        self.organ_pool.register("cat_morphology", self._build_cat_organ)
        self.organ_pool.register("scientific_dna", self._build_dna_organ)

    @staticmethod
    def _bindings():
        from fap_media_lab.runtime import ActualFileObserver, ArtifactIntegrityCritic
        from fap_observed_media import ObserverBinding
        return (
            {
                "image": (
                    ObserverBinding(
                        "actual_file_evidence",
                        ActualFileObserver(),
                        ("image",),
                    ),
                )
            },
            {"image": (ArtifactIntegrityCritic(),)},
        )

    def _build_scene_organ(self):
        from fap_scene_graph2 import SceneGraph2Manager
        from fap_sparse_execution import activate_sparse_renderers
        activate_sparse_renderers(("scene_graph2",))
        observers, critics = self._bindings()
        return SceneGraph2Manager(
            artifact_dir=base.ARTIFACTS,
            observer_bindings=observers,
            integrity_critics=critics,
        )

    def _build_cat_organ(self):
        from fap_morphology import MorphologyManager
        from fap_sparse_execution import activate_sparse_renderers
        activate_sparse_renderers(("morphology",))
        observers, critics = self._bindings()
        return MorphologyManager(
            artifact_dir=base.ARTIFACTS,
            observer_bindings=observers,
            integrity_critics=critics,
        )

    def _build_dna_organ(self):
        from fap_scientific_geometry import ScientificGeometryManager
        from fap_sparse_execution import activate_sparse_renderers
        activate_sparse_renderers(("scientific_dna",))
        observers, critics = self._bindings()
        return ScientificGeometryManager(
            artifact_dir=base.ARTIFACTS,
            observer_bindings=observers,
            integrity_critics=critics,
        )

    def capabilities(self):
        caps = super().capabilities()
        for item in [
            "latest-mainline-chat:v87.37",
            "v82-sparse-organ-routing",
            "lazy-media-organs",
            "sparse-tile-renderer",
            "cached-finished-background",
            "scientific-fast-renderer",
            "active-tile-fxaa",
            "active-pixel-filmic",
            "v87.34-scene-graph2",
            "v87.35-cat-morphology",
            "v87.36-scientific-dna",
        ]:
            if item not in caps:
                caps.append(item)
        return caps

    def status(self):
        out = super().status()
        out.update({
            "version": VERSION,
            "mainline_version": "87.37",
            "state": "ready",
            "sparse_execution": {
                "router": "V82 SparseRouter",
                "top_k": 1,
                "organs_registered": [
                    "scene",
                    "cat_morphology",
                    "scientific_dna",
                ],
                "organs_loaded": list(self.organ_pool.loaded()),
                "organ_load_count": self.organ_pool.load_count,
                "renderer_loaded": "fap_sparse_execution.renderer" in sys.modules,
                "tile_size": 32,
            },
            "chat_stack": {
                "general_chat": "V87.12 semantic/adaptive fast path",
                "structured_reasoning": "V87.25-V87.28",
                "media_router": "V82 verifier-first sparse router",
                "scene": "V87.34 lazy",
                "cat_morphology": "V87.35 lazy",
                "scientific_dna": "V87.36 lazy",
                "renderer": "V87.37 sparse tile / scientific fast path",
            },
        })
        out["capabilities"] = self.capabilities()
        return out

    def _latest_image_capability(self):
        return {
            "ok": True,
            "reply": (
                "V87.37 Sparse End-to-End画像系を使用できます。"
                "\nV82 SparseRouterが必要な器官を1つだけ発火させ、"
                "未使用器官は初回利用までロードしません。"
                "\nscene=V87.34 / cat=V87.35 / DNA=V87.36"
                "\nrender=32px sparse tiles + cached background; DNAはscientific fast pathです。"
            ),
            "confidence": 0.99,
        }

    @staticmethod
    def _constraints(text: str) -> tuple[str, ...]:
        low = text.lower()
        out = []
        if any(x in low for x in (
            "写真風", "フォトリアル", "photoreal", "photo-real", "photographic"
        )):
            out.append("写真風")
        if any(x in low for x in (
            "イラスト", "アニメ", "illustration", "anime", "cartoon"
        )):
            out.append("イラスト")
        if "中央" in text or "center" in low:
            out.append("被写体を中央に保つ")
        return tuple(out)

    def _latest_image_generate(self, text: str):
        from fap_media_generation import GenerationRequest
        from fap_sparse_execution import last_render_stats

        prompt = self.image.prompt_from(text).strip()
        if prompt.endswith("の"):
            prompt = prompt[:-1].rstrip()
        prompt = prompt or text.strip()

        route = self.organ_router.route(text)
        manager = self.organ_pool.get(route.organ_id)
        attempts = 2 if route.organ_id == "scene" else 1
        request = GenerationRequest(
            prompt=prompt,
            media_type="image",
            width=768,
            height=768,
            max_attempts=attempts,
            min_score=0.99,
            constraints=self._constraints(text),
        )

        try:
            run = manager.generate(request)
        except Exception as exc:
            return {
                "ok": False,
                "reply": "V87.37 sparse media organ failed: " + base.compact(exc),
                "confidence": 0.75,
                "artifacts": [],
                "sparse_route": route.__dict__,
            }

        result = run.result
        candidate = result.best_candidate
        if candidate is None:
            return {
                "ok": False,
                "reply": "V87.37で候補を生成できませんでした。",
                "confidence": 0.5,
                "artifacts": [],
                "sparse_route": route.__dict__,
            }

        artifact = candidate.artifact
        issues = [i.code for i in candidate.critique.issues]
        url = "/artifacts/" + Path(artifact.locator).name
        accepted = bool(result.accepted)
        render_stats = last_render_stats()

        labels = {
            "scene": "V87.34 Scene Graph 2",
            "cat_morphology": "V87.35 Morphology",
            "scientific_dna": "V87.36 Scientific Geometry",
        }
        reply = (
            f"{labels.get(route.organ_id, route.organ_id)}をV87.37疎実行で生成・検証しました。"
            if accepted
            else f"{labels.get(route.organ_id, route.organ_id)}をV87.37疎実行で生成しましたが、検証はNOT ACCEPTEDです。"
        )
        reply += (
            f"\nactive organ={route.organ_id}"
            f" / active tiles={render_stats.get('active_tiles', '?')}"
            f"/{render_stats.get('total_tiles', '?')}"
        )
        if issues:
            reply += "\nissues: " + ", ".join(issues)

        return {
            "ok": accepted,
            "reply": reply,
            "confidence": 0.99 if accepted else max(
                0.58, float(candidate.critique.score)
            ),
            "artifacts": [{"type": "image", "src": url, "name": Path(url).name}],
            "sparse_route": {
                **route.__dict__,
                "loaded_organs": list(self.organ_pool.loaded()),
                "organ_load_count": self.organ_pool.load_count,
            },
            "sparse_render": render_stats,
            "media": {
                "accepted": accepted,
                "status": result.status,
                "backend_id": candidate.backend_id,
                "score": float(candidate.critique.score),
                "issues": issues,
                "metadata": artifact.metadata,
            },
        }

    def route(self, intent, text: str, history: list[dict]):
        if intent.name == "image_capability":
            return self._latest_image_capability()
        if intent.name == "image_generate":
            return self._latest_image_generate(text)
        return super().route(intent, text, history)


CORE = FAPV8737Unified()
v28.CORE = CORE
v28.v27.CORE = CORE
v28.v27.v26.CORE = CORE
v28.v27.v26.v25.CORE = CORE
v28.v27.v26.v25.v12.CORE = CORE
base.CORE = CORE
base.VERSION = VERSION


class Handler(v28.Handler):
    server_version = "FAPV87.37Sparse"


def main():
    if not base.WEB_FILE.exists():
        raise SystemExit(f"missing UI: {base.WEB_FILE}")
    print("FAP V87.37 SPARSE END-TO-END")
    print(f"UI: http://{base.HOST}:{base.PORT}/")
    print("Media organs are lazy and V82 sparse-routed.")
    print("Rendering uses active tiles; DNA uses scientific fast renderer.")
    print("Qwen: not used")
    ThreadingHTTPServer((base.HOST, base.PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
