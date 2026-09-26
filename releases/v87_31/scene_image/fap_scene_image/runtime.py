from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import MediaLabRuntime


def _critics_by_kind(critique) -> dict[str, dict]:
    out = {}
    for value in dict(getattr(critique, "evidence", {}) or {}).values():
        if isinstance(value, dict):
            kind = str(value.get("kind", ""))
            if kind:
                out[kind] = value
    return out


class SceneMediaLabRuntime(MediaLabRuntime):
    def status(self) -> dict:
        engines = self.manager.status()
        return {
            "name": "FAP MEDIA LAB",
            "version": "87.31",
            "state": "ready" if engines else "needs_engine",
            "skills": [
                {
                    "skill_id": f"media.generate.image:{e['engine_id']}",
                    "engine_id": e["engine_id"],
                    "media_type": "image",
                    "stage": "fap-native-scene-compliance",
                    "score_ema": 0.0,
                    "verified_successes": 0,
                    "verified_failures": 0,
                    "credential_present": True,
                    "endpoint_origin": "none",
                    "adapter": "fap-scene-image",
                    "model_id": e["model_id"],
                    "license_id": e["license_id"],
                    "supported_scene_objects": e["supported_scene_objects"],
                    "render_style": e["render_style"],
                    "semantic_gate": e["semantic_gate"],
                    "style_gate": e["style_gate"],
                }
                for e in engines
            ],
            "artifact_dir": str(self.artifact_dir),
            "offline": True,
            "network_fallback": False,
            "external_model_required": False,
            "fap_owned_engine": True,
            "verification": {
                "current": "artifact-integrity + scene-quality",
                "semantic_quality": True,
                "style_capability_gate": True,
                "note": "Artifact integrity, required scene objects, centered-layout constraints and requested style capability are evaluated separately.",
            },
        }

    def generate(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        prompt = str(payload.get("prompt", "")).strip()
        media_type = str(payload.get("media_type", "image")).strip().lower()
        if not prompt:
            raise ValueError("prompt is required")
        if media_type != "image":
            raise ValueError("V87.31 scene image lab currently supports image only")

        constraints_raw = payload.get("constraints", ())
        if isinstance(constraints_raw, str):
            constraints = tuple(x.strip() for x in constraints_raw.split("\n") if x.strip())
        elif isinstance(constraints_raw, (list, tuple)):
            constraints = tuple(str(x).strip() for x in constraints_raw if str(x).strip())
        else:
            raise ValueError("constraints must be text or list")

        request = GenerationRequest(
            prompt=prompt,
            media_type="image",
            width=int(payload.get("width", 1024)),
            height=int(payload.get("height", 1024)),
            max_attempts=int(payload.get("max_attempts", 3)),
            min_score=0.99,
            constraints=constraints,
        )
        run = self.manager.generate(request)
        result = run.result
        candidate = result.best_candidate
        response = {
            "accepted": bool(result.accepted),
            "status": result.status,
            "stop_reason": result.stop_reason,
            "generator_calls": result.generator_calls,
            "rounds": len(result.rounds),
            "updated_skills": list(run.updated_skills),
            "artifact": None,
        }
        if candidate is None:
            return response

        artifact = candidate.artifact
        path = Path(artifact.locator)
        by_kind = _critics_by_kind(candidate.critique)
        integrity = by_kind.get("artifact-integrity", {})
        scene = by_kind.get("scene-quality", {})
        response["artifact"] = {
            "media_type": artifact.media_type,
            "mime_type": artifact.mime_type,
            "digest": artifact.digest,
            "filename": path.name,
            "url": "/artifacts/" + path.name,
            "backend_id": candidate.backend_id,
            "verification_score": float(candidate.critique.score),
            "verification_kind": "artifact-integrity + scene-quality",
            "integrity_score": float(integrity.get("score", 1.0 if integrity.get("digest_match") else 0.0)),
            "object_score": float(scene.get("object_score", 0.0)),
            "layout_score": float(scene.get("layout_score", 0.0)),
            "style_score": float(scene.get("style_score", 0.0)),
            "required_objects": list(scene.get("required_objects", [])),
            "generated_objects": list(scene.get("generated_objects", [])),
            "missing_objects": list(scene.get("missing_objects", [])),
            "requested_styles": list(scene.get("requested_styles", [])),
            "render_style": scene.get("render_style", artifact.metadata.get("render_style", "")),
            "issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "detail": issue.detail,
                }
                for issue in candidate.critique.issues
            ],
        }
        return response
