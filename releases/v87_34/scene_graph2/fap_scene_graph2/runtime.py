from __future__ import annotations

from pathlib import Path
from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import MediaLabRuntime


def _quality(critique):
    for value in dict(getattr(critique, "evidence", {}) or {}).values():
        if isinstance(value, dict) and value.get("kind") == "scene-graph2-quality":
            return value
    return {}


class SceneGraph2Runtime(MediaLabRuntime):
    def status(self) -> dict:
        e = self.manager.status()[0]
        return {
            "name": "FAP MEDIA LAB",
            "version": "87.34",
            "state": "ready",
            "skills": [{
                "skill_id": f"media.generate.image:{e['engine_id']}",
                "engine_id": e["engine_id"],
                "media_type": "image",
                "stage": "scene-graph2",
                "supported_scene_objects": e["supported_scene_objects"],
                "supports": e["supports"],
                "render_style": e["render_style"],
            }],
            "offline": True,
            "network_fallback": False,
            "fap_owned_engine": True,
        }

    def generate(self, payload: dict) -> dict:
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required")
        raw = payload.get("constraints", ())
        if isinstance(raw, str):
            constraints = tuple(x.strip() for x in raw.split("\n") if x.strip())
        elif isinstance(raw, (list, tuple)):
            constraints = tuple(str(x).strip() for x in raw if str(x).strip())
        else:
            raise ValueError("constraints must be text or list")

        req = GenerationRequest(
            prompt=prompt,
            media_type="image",
            width=int(payload.get("width", 1024)),
            height=int(payload.get("height", 1024)),
            max_attempts=int(payload.get("max_attempts", 2)),
            min_score=0.99,
            constraints=constraints,
        )
        run = self.manager.generate(req)
        result = run.result
        candidate = result.best_candidate
        out = {
            "accepted": bool(result.accepted),
            "status": result.status,
            "generator_calls": result.generator_calls,
            "constraints_received": list(constraints),
            "artifact": None,
        }
        if candidate is None:
            return out
        q = _quality(candidate.critique)
        a = candidate.artifact
        p = Path(a.locator)
        out["artifact"] = {
            "url": "/artifacts/" + p.name,
            "backend_id": candidate.backend_id,
            "verification_score": float(candidate.critique.score),
            "count_score": float(q.get("count_score", 0.0)),
            "attribute_score": float(q.get("attribute_score", 0.0)),
            "state_score": float(q.get("state_score", 0.0)),
            "relation_score": float(q.get("relation_score", 0.0)),
            "negative_score": float(q.get("negative_score", 0.0)),
            "viewpoint_score": float(q.get("viewpoint_score", 0.0)),
            "style_score": float(q.get("style_score", 0.0)),
            "required_counts": q.get("required_counts", {}),
            "generated_counts": q.get("generated_counts", {}),
            "forbidden_kinds": q.get("forbidden_kinds", []),
            "required_relations": q.get("required_relations", []),
            "applied_relations": q.get("applied_relations", []),
            "requested_viewpoint": q.get("requested_viewpoint", ""),
            "applied_viewpoint": q.get("applied_viewpoint", ""),
            "scene_graph2": a.metadata.get("scene_graph2", {}),
            "issues": [
                {"code": i.code, "severity": i.severity, "detail": i.detail}
                for i in candidate.critique.issues
            ],
        }
        return out
