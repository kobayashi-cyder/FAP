from __future__ import annotations

from typing import Sequence

from fap_human_lbs.core import Mesh
from fap_scene_image.scene import add_static_ellipsoid


Vec3 = tuple[float, float, float]


def _append_new_positions(mesh: Mesh, positions: list[Vec3], start: int) -> None:
    positions.extend(v.bind_position for v in mesh.vertices[start:])


def augment_surface_details(
    mesh: Mesh,
    positions: list[Vec3],
    *,
    generated_objects: Sequence[str],
    scene_details: dict,
) -> dict:
    """Add small native surface details after pose deformation.

    V87.30 intentionally kept the human head as a plain ellipsoid. V87.32 adds
    face/hair primitives in world space so the photo-look renderer has actual
    geometry to shade instead of trying to fake detail in 2D.
    """
    added = {
        "human_face_detail": False,
        "human_hair_detail": False,
    }

    if "human" not in set(generated_objects):
        return added

    info = dict(scene_details.get("human", {}))
    offset = info.get("offset", (0.0, 0.0, 0.0))
    ox = float(offset[0]) if len(offset) >= 1 else 0.0

    # Hair cap: deliberately sits high/back so it does not cover the full face.
    start = len(mesh.vertices)
    add_static_ellipsoid(
        mesh,
        (ox, 2.105, 0.055),
        (0.255, 0.185, 0.225),
        (72, 53, 43),
        rings=7,
        sides=12,
    )
    _append_new_positions(mesh, positions, start)
    added["human_hair_detail"] = True

    # Eyes, nose, mouth and ears. Camera-front is negative Z in the native
    # renderer, so face features are placed on the negative-Z hemisphere.
    face_parts = (
        ((ox - 0.082, 2.020, -0.226), (0.025, 0.019, 0.018), (38, 31, 28)),
        ((ox + 0.082, 2.020, -0.226), (0.025, 0.019, 0.018), (38, 31, 28)),
        ((ox, 1.970, -0.248), (0.038, 0.050, 0.031), (197, 146, 119)),
        ((ox, 1.895, -0.235), (0.060, 0.014, 0.012), (121, 72, 68)),
        ((ox - 0.247, 1.985, 0.0), (0.035, 0.075, 0.050), (203, 157, 130)),
        ((ox + 0.247, 1.985, 0.0), (0.035, 0.075, 0.050), (203, 157, 130)),
    )
    for center, radii, color in face_parts:
        start = len(mesh.vertices)
        add_static_ellipsoid(
            mesh,
            center,
            radii,
            color,
            rings=5,
            sides=9,
        )
        _append_new_positions(mesh, positions, start)

    added["human_face_detail"] = True
    return added
