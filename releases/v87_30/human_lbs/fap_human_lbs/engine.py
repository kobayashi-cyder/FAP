from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from fap_media_generation import GenerationRequest, MediaArtifact

from .core import (
    build_human_mesh,
    default_human_skeleton,
    pose_from_prompt,
    render_human_png,
    view_from_prompt,
)


class HumanLBSError(RuntimeError):
    pass


class HumanLBSEngine:
    """FAP-native articulated human renderer using linear blend skinning.

    The engine owns the skeleton, bind pose, vertex weights, LBS deformation,
    software projection, z-buffer and PNG encoding path. It does not require an
    external image model or pretrained checkpoint.
    """

    def __init__(self, *, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.engine_id = "fap-human-lbs-v1"
        self.skeleton = default_human_skeleton()
        self.mesh = build_human_mesh(self.skeleton)

    def probe(self) -> dict:
        weighted = sum(1 for v in self.mesh.vertices if len(v.weights) > 1)
        return {
            "engine_id": self.engine_id,
            "model_id": "fap-human-lbs-v1",
            "license_id": "project-native",
            "offline": True,
            "external_weights": False,
            "external_runtime": False,
            "stdlib_only": True,
            "generation_kind": "skeletal-linear-blend-skinning",
            "bones": len(self.skeleton.bones),
            "vertices": len(self.mesh.vertices),
            "faces": len(self.mesh.faces),
            "multi_bone_vertices": weighted,
        }

    def generate(self, request: GenerationRequest, *, prompt: str, previous, critique) -> MediaArtifact:
        request.validate()
        if request.media_type != "image":
            raise HumanLBSError("human LBS engine supports images only")
        text = prompt.strip()
        pose = pose_from_prompt(text)
        yaw, pitch = view_from_prompt(text)
        data = render_human_png(
            self.mesh,
            self.skeleton,
            pose,
            width=request.width,
            height=request.height,
            yaw_deg=yaw,
            pitch_deg=pitch,
        )
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HumanLBSError("renderer did not produce PNG")
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
                "adapter": "fap-human-lbs",
                "model_id": "fap-human-lbs-v1",
                "offline": True,
                "external_weights": False,
                "stdlib_only": True,
                "bytes": len(data),
                "bones": len(self.skeleton.bones),
                "vertices": len(self.mesh.vertices),
                "faces": len(self.mesh.faces),
                "view_yaw_deg": yaw,
                "view_pitch_deg": pitch,
                "pose_bones": sorted(pose.rotations),
            },
        )
