from __future__ import annotations

from pathlib import Path
from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import MediaLabRuntime


def _critic(critique):
    for value in dict(getattr(critique, "evidence", {}) or {}).values():
        if isinstance(value, dict) and value.get("kind") == "object-registry-quality":
            return value
    return {}


class ObjectRegistryRuntime(MediaLabRuntime):
    def status(self) -> dict:
        e = self.manager.status()[0]
        return {
            "name": "FAP MEDIA LAB",
            "version": "87.33",
            "state": "ready",
            "skills": [{
                "skill_id": f"media.generate.image:{e['engine_id']}",
                "engine_id": e["engine_id"],
                "media_type": "image",
                "stage": "fap-object-registry-photo-look",
                "supported_scene_objects": e["supported_scene_objects"],
                "render_style": e["render_style"],
                "photo_look_capability": e["photo_look_capability"],
                "learned_refiner": e["learned_refiner"],
            }],
            "offline": True,
            "network_fallback": False,
            "external_model_required": False,
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
            "rounds": len(result.rounds),
            "constraints_received": list(constraints),
            "artifact": None,
        }
        if candidate is None:
            return out
        q = _critic(candidate.critique)
        a = candidate.artifact
        p = Path(a.locator)
        out["artifact"] = {
            "url": "/artifacts/" + p.name,
            "backend_id": candidate.backend_id,
            "integrity_score": 1.0,
            "object_score": float(q.get("object_score", 0.0)),
            "layout_score": float(q.get("layout_score", 0.0)),
            "style_score": float(q.get("style_score", 0.0)),
            "photo_look_capability": float(q.get("photo_look_capability", 0.0)),
            "photorealistic_verified": bool(q.get("photorealistic_verified", False)),
            "required_objects": list(q.get("required_objects", [])),
            "generated_objects": list(q.get("generated_objects", [])),
            "missing_objects": list(q.get("missing_objects", [])),
            "requested_styles": list(q.get("requested_styles", [])),
            "render_style": q.get("render_style", ""),
            "photo_look_features": list(q.get("photo_look_features", [])),
            "verification_score": float(candidate.critique.score),
            "issues": [{"code": i.code, "severity": i.severity, "detail": i.detail} for i in candidate.critique.issues],
        }
        return out
