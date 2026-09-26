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


class PhotoLookMediaLabRuntime(MediaLabRuntime):
    def status(self) -> dict:
        engines = self.manager.status()
        return {
            "name": "FAP MEDIA LAB",
            "version": "87.32",
            "state": "ready" if engines else "needs_engine",
            "skills": [
                {
                    "skill_id": f"media.generate.image:{e['engine_id']}",
                    "engine_id": e["engine_id"],
                    "media_type": "image",
                    "stage": "fap-native-photo-look",
                    "credential_present": True,
                    "endpoint_origin": "none",
                    "adapter": "fap-photo-look",
                    "model_id": e["model_id"],
                    "license_id": e["license_id"],
                    "supported_scene_objects": e["supported_scene_objects"],
                    "render_style": e["render_style"],
                    "photo_look_capability": e["photo_look_capability"],
                    "learned_refiner": e["learned_refiner"],
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
                "current": "artifact-integrity + photo-look-quality",
                "semantic_quality": True,
                "style_capability_gate": True,
                "photorealistic_verified": False,
                "note": "V87.32 has native photo-look improvements but still rejects true photorealistic requests until a verified learned refiner exists.",
            },
        }

    def generate(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required")

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
        quality = by_kind.get("photo-look-quality", {})
        response["artifact"] = {
            "media_type": artifact.media_type,
            "mime_type": artifact.mime_type,
            "digest": artifact.digest,
            "filename": path.name,
            "url": "/artifacts/" + path.name,
            "backend_id": candidate.backend_id,
            "verification_score": float(candidate.critique.score),
            "verification_kind": "artifact-integrity + photo-look-quality",
            "integrity_score": float(integrity.get("score", 1.0 if integrity.get("digest_match") else 0.0)),
            "object_score": float(quality.get("object_score", 0.0)),
            "layout_score": float(quality.get("layout_score", 0.0)),
            "style_score": float(quality.get("style_score", 0.0)),
            "photo_look_capability": float(quality.get("photo_look_capability", 0.0)),
            "photorealistic_verified": bool(quality.get("photorealistic_verified", False)),
            "required_objects": list(quality.get("required_objects", [])),
            "generated_objects": list(quality.get("generated_objects", [])),
            "missing_objects": list(quality.get("missing_objects", [])),
            "requested_styles": list(quality.get("requested_styles", [])),
            "render_style": quality.get("render_style", artifact.metadata.get("render_style", "")),
            "photo_look_features": list(quality.get("photo_look_features", [])),
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
