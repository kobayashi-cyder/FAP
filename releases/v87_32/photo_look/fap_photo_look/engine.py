from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from fap_media_generation import GenerationRequest, MediaArtifact
from fap_scene_image import SceneImageEngine
from fap_scene_image.scene import (
    build_scene_geometry,
    parse_scene_plan,
    requested_view,
)

from .detail import augment_surface_details
from .renderer import render_photo_look_png


class PhotoLookError(RuntimeError):
    pass


class PhotoLookEngine:
    """V87.32 native appearance renderer.

    This layer improves geometric appearance without pretending to be a learned
    photorealistic model. It preserves V87.31 scene semantics and fail-closed
    object/style accounting.
    """

    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-photo-look-v1"
        self.scene_fallback = SceneImageEngine(artifact_dir=self.artifact_dir)

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-photo-look-v1",
            "license_id": "project-native",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "generation_kind": "scene-graph-native-photo-look-renderer",
            "supported_scene_objects": ["human", "dog"],
            "render_style": "photo-look-native",
            "photo_look_capability": 0.58,
            "learned_refiner": False,
            "semantic_gate": True,
            "style_gate": True,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != "image":
            raise PhotoLookError("photo-look engine supports images only")

        plan = parse_scene_plan(prompt, request.constraints)

        # Keep all prior procedural coverage for prompts that do not request
        # explicit semantic scene objects.
        if not plan.required_objects:
            fallback = self.scene_fallback.generate(
                request,
                prompt=prompt,
                previous=previous,
                critique=critique,
            )
            metadata = dict(fallback.metadata)
            metadata.update({
                "engine_id": self.engine_id,
                "adapter": "fap-photo-look-fallback",
                "model_id": "fap-photo-look-v1",
                "photo_look_capability": 0.0,
                "learned_refiner": False,
                "photo_look_features": [],
            })
            return replace(fallback, metadata=metadata)

        mesh, positions, generated, details = build_scene_geometry(plan, prompt)
        surface_detail = augment_surface_details(
            mesh,
            positions,
            generated_objects=generated,
            scene_details=details,
        )
        yaw, pitch = requested_view(plan.source_text)
        data, render_features = render_photo_look_png(
            mesh,
            positions,
            generated_objects=generated,
            width=request.width,
            height=request.height,
            yaw_deg=yaw,
            pitch_deg=pitch,
        )
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise PhotoLookError("renderer did not produce PNG")

        digest = sha256(data).hexdigest()
        path = self.artifact_dir / f"{digest}.png"
        path.write_bytes(data)

        applied_constraints = []
        if plan.centered_subjects:
            applied_constraints.append("centered_subjects")

        features = {
            **render_features,
            **surface_detail,
        }

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(path),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "fap-photo-look",
                "model_id": "fap-photo-look-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "bytes": len(data),
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
                "photo_look_features": [k for k, enabled in features.items() if enabled],
                "view_yaw_deg": yaw,
                "view_pitch_deg": pitch,
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
            },
        )
