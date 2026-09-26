from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from fap_media_generation import GenerationRequest, MediaArtifact
from fap_photo_look import augment_surface_details, render_photo_look_png, PhotoLookEngine

from .registry import build_scene_geometry, parse_scene_plan, supported_object_names


class ObjectRegistryEngine:
    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-object-registry-v1"
        self.fallback = PhotoLookEngine(artifact_dir=self.artifact_dir)

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-object-registry-v1",
            "license_id": "project-native",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "generation_kind": "scene-object-registry-photo-look",
            "supported_scene_objects": list(supported_object_names()),
            "render_style": "photo-look-native",
            "photo_look_capability": 0.58,
            "photorealistic_verified": False,
            "learned_refiner": False,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        plan = parse_scene_plan(prompt, request.constraints)
        if not plan.required_objects:
            fallback = self.fallback.generate(
                request, prompt=prompt, previous=previous, critique=critique
            )
            meta = dict(fallback.metadata)
            meta.update({
                "engine_id": self.engine_id,
                "adapter": "fap-object-registry-fallback",
                "model_id": "fap-object-registry-v1",
                "supported_scene_objects": list(supported_object_names()),
            })
            return replace(fallback, metadata=meta)

        mesh, positions, generated, details = build_scene_geometry(plan, prompt)
        surface_detail = augment_surface_details(
            mesh,
            positions,
            generated_objects=generated,
            scene_details=details,
        )

        data, features = render_photo_look_png(
            mesh,
            positions,
            generated_objects=generated,
            width=request.width,
            height=request.height,
            yaw_deg=0.0,
            pitch_deg=-4.0,
        )
        digest = sha256(data).hexdigest()
        path = self.artifact_dir / f"{digest}.png"
        path.write_bytes(data)

        applied_constraints = []
        if plan.centered_subjects:
            applied_constraints.append("centered_subjects")

        feature_map = {**features, **surface_detail}

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(path),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "fap-object-registry",
                "model_id": "fap-object-registry-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "scene_required_objects": list(plan.required_objects),
                "generated_objects": list(generated),
                "unsupported_objects": list(plan.unsupported_objects),
                "requested_styles": list(plan.requested_styles),
                "render_style": "photo-look-native",
                "photo_look_capability": 0.58,
                "photorealistic_verified": False,
                "learned_refiner": False,
                "centered_subjects": bool(plan.centered_subjects),
                "applied_constraints": applied_constraints,
                "scene_details": details,
                "photo_look_features": [k for k, enabled in feature_map.items() if enabled],
                "supported_scene_objects": list(supported_object_names()),
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
            },
        )
