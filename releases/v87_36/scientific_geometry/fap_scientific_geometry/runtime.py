from __future__ import annotations

from pathlib import Path

from fap_media_generation import GenerationRequest
from fap_media_lab.runtime import MediaLabRuntime


def _quality(critique):
    for value in dict(getattr(critique, "evidence", {}) or {}).values():
        if isinstance(value, dict) and value.get("kind") == "scientific-geometry":
            return value
    return {}


class ScientificGeometryRuntime(MediaLabRuntime):
    def status(self):
        e = self.manager.status()[0]
        return {
            "name": "FAP SCIENTIFIC GEOMETRY LAB",
            "version": "87.36",
            "state": "ready",
            "skills": [{
                "engine_id": e["engine_id"],
                "media_type": "image",
                "scientific_objects": e["scientific_objects"],
                "verified_dna_form": e["verified_dna_form"],
                "coordinate_system": e["coordinate_system"],
            }],
            "offline": True,
            "fap_owned_engine": True,
        }

    def generate(self, payload: dict):
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required")
        raw = payload.get("constraints", ())
        if isinstance(raw, str):
            constraints = tuple(x.strip() for x in raw.split("\n") if x.strip())
        else:
            constraints = tuple(str(x).strip() for x in raw if str(x).strip())
        req = GenerationRequest(
            prompt=prompt,
            media_type="image",
            width=int(payload.get("width", 768)),
            height=int(payload.get("height", 768)),
            max_attempts=1,
            min_score=0.99,
            constraints=constraints,
        )
        run = self.manager.generate(req)
        result = run.result
        candidate = result.best_candidate
        out = {"accepted": bool(result.accepted), "status": result.status, "artifact": None}
        if candidate is None:
            return out
        q = _quality(candidate.critique)
        a = candidate.artifact
        p = Path(a.locator)
        out["artifact"] = {
            "url": "/artifacts/" + p.name,
            "backend_id": candidate.backend_id,
            "verification_score": float(candidate.critique.score),
            "scientific": q,
            "geometry": a.metadata.get("scientific_geometry", {}),
            "issues": [
                {"code": i.code, "severity": i.severity, "detail": i.detail}
                for i in candidate.critique.issues
            ],
        }
        return out
