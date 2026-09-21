from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from fap_media_generation import GenerationRequest, MediaArtifact
from fap_native_image import NativeImageEngine

from .scene import (
    build_scene_geometry,
    parse_scene_plan,
    render_scene_png,
    requested_view,
)


class SceneImageError(RuntimeError):
    pass


class SceneImageEngine:
    """Prompt-aware scene generator with structural object accounting.

    Human and dog requests are rendered through explicit native 3D geometry.
    Other prompts fall back to the V87.29 procedural raster engine so V87.31
    does not erase earlier prompt-to-raster coverage.
    """

    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-scene-image-v1"
        self.fallback = NativeImageEngine(artifact_dir=self.artifact_dir)

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-scene-image-v1",
            "license_id": "project-native",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "generation_kind": "scene-graph-native-3d-with-raster-fallback",
            "supported_scene_objects": ["human", "dog"],
            "render_style": "geometric-3d",
            "semantic_gate": True,
            "style_gate": True,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != "image":
            raise SceneImageError("scene image engine supports images only")

        plan = parse_scene_plan(prompt, request.constraints)

        # Preserve V87.29 coverage when this scene engine has no recognized
        # semantic object to construct.
        if not plan.required_objects:
            fallback = self.fallback.generate(
                request,
                prompt=prompt,
                previous=previous,
                critique=critique,
            )
            metadata = dict(fallback.metadata)
            metadata.update({
                "engine_id": self.engine_id,
                "adapter": "fap-scene-image-fallback",
                "model_id": "fap-scene-image-v1",
                "scene_required_objects": [],
                "generated_objects": [],
                "unsupported_objects": [],
                "requested_styles": list(plan.requested_styles),
                "render_style": "procedural-2d",
                "centered_subjects": bool(plan.centered_subjects),
                "applied_constraints": [],
                "scene_mode": "v87.29-raster-fallback",
            })
            return replace(fallback, metadata=metadata)

        mesh, positions, generated, details = build_scene_geometry(plan, prompt)
        yaw, pitch = requested_view(plan.source_text)
        data = render_scene_png(
            mesh,
            positions,
            width=request.width,
            height=request.height,
            yaw_deg=yaw,
            pitch_deg=pitch,
        )
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise SceneImageError("scene renderer did not produce PNG")

        digest = sha256(data).hexdigest()
        path = self.artifact_dir / f"{digest}.png"
        path.write_bytes(data)

        applied_constraints = []
        if plan.centered_subjects:
            applied_constraints.append("centered_subjects")

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(path),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "fap-scene-image",
                "model_id": "fap-scene-image-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "bytes": len(data),
                "scene_required_objects": list(plan.required_objects),
                "generated_objects": list(generated),
                "unsupported_objects": list(plan.unsupported_objects),
                "requested_styles": list(plan.requested_styles),
                "render_style": "geometric-3d",
                "centered_subjects": bool(plan.centered_subjects),
                "applied_constraints": applied_constraints,
                "scene_details": details,
                "view_yaw_deg": yaw,
                "view_pitch_deg": pitch,
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
            },
        )
