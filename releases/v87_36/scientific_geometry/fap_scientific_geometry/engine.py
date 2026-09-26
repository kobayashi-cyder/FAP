from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from fap_media_generation import GenerationRequest, MediaArtifact
from fap_photo_look import render_photo_look_png

from .dna import build_dna_mesh, parse_dna_request, view_angles


class ScientificGeometryEngine:
    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-scientific-geometry-v1"

    def probe(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-scientific-geometry-v1",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "scientific_objects": ["dna"],
            "verified_dna_form": "B-DNA",
            "coordinate_system": "parametric-nm",
            "render_style": "scientific-3d",
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        spec = parse_dna_request(prompt, request.constraints)
        mesh, positions, scientific = build_dna_mesh(spec)
        yaw, pitch = view_angles(spec.viewpoint)
        data, features = render_photo_look_png(
            mesh,
            positions,
            generated_objects=("dna",),
            width=request.width,
            height=request.height,
            yaw_deg=yaw,
            pitch_deg=pitch,
        )
        digest = sha256(data).hexdigest()
        path = self.artifact_dir / f"{digest}.png"
        path.write_bytes(data)

        return MediaArtifact(
            media_type="image",
            digest=digest,
            mime_type="image/png",
            locator=str(path),
            metadata={
                "engine_id": self.engine_id,
                "adapter": "fap-scientific-geometry",
                "model_id": "fap-scientific-geometry-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "generated_objects": ["dna"],
                "scientific_geometry": scientific,
                "requested_viewpoint": spec.viewpoint,
                "applied_viewpoint": spec.viewpoint,
                "view_yaw_deg": yaw,
                "view_pitch_deg": pitch,
                "render_style": "scientific-3d",
                "photo_look_features": [k for k, v in features.items() if v],
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
            },
        )
