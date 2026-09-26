from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Sequence

from fap_human_lbs.core import (
    Face,
    Mesh,
    Pose,
    RGBImage,
    Vertex,
    build_human_mesh,
    default_human_skeleton,
    pose_from_prompt,
    skinned_positions,
    v_add,
    v_cross,
    v_dot,
    v_len,
    v_norm,
    v_scale,
    v_sub,
    view_from_prompt,
)


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class ScenePlan:
    required_objects: tuple[str, ...]
    supported_objects: tuple[str, ...]
    unsupported_objects: tuple[str, ...]
    requested_styles: tuple[str, ...]
    centered_subjects: bool
    source_text: str


_OBJECT_PATTERNS = (
    ("human", re.compile(r"(?:^|[^A-Za-z])(?:人|人物|人間|男性|女性|男の人|女の人)(?:$|[^A-Za-z])|\b(?:person|people|human|man|woman)\b", re.I)),
    ("dog", re.compile(r"犬|わんこ|ワンコ|ビーグル|\b(?:dog|beagle|puppy)\b", re.I)),
    ("cat", re.compile(r"猫|ネコ|ねこ|\bcat\b", re.I)),
    ("car", re.compile(r"車|自動車|\bcar\b", re.I)),
    ("bird", re.compile(r"鳥|\bbird\b", re.I)),
    ("horse", re.compile(r"馬|\bhorse\b", re.I)),
)
_SUPPORTED = {"human", "dog"}


def parse_scene_plan(prompt: str, constraints: Sequence[str] = ()) -> ScenePlan:
    text = "\n".join([str(prompt or ""), *(str(x or "") for x in constraints)])
    required: list[str] = []
    for kind, pattern in _OBJECT_PATTERNS:
        if pattern.search(text):
            required.append(kind)

    styles: list[str] = []
    if re.search(r"写真風|写真のよう|フォトリアル|写実|実写|\b(?:photo|photoreal|photorealistic|realistic photo)\b", text, re.I):
        styles.append("photorealistic")
    if re.search(r"イラスト|漫画|アニメ|\b(?:illustration|anime|cartoon)\b", text, re.I):
        styles.append("illustration")
    if not styles:
        styles.append("geometric-3d")

    centered = bool(re.search(r"中央|中心|センター|\bcenter(?:ed)?\b", text, re.I))
    supported = [x for x in required if x in _SUPPORTED]
    unsupported = [x for x in required if x not in _SUPPORTED]
    return ScenePlan(
        required_objects=tuple(required),
        supported_objects=tuple(supported),
        unsupported_objects=tuple(unsupported),
        requested_styles=tuple(styles),
        centered_subjects=centered,
        source_text=text,
    )


def _basis(tangent: Vec3) -> tuple[Vec3, Vec3]:
    t = v_norm(tangent)
    ref = (0.0, 0.0, 1.0)
    if abs(v_dot(t, ref)) > 0.93:
        ref = (1.0, 0.0, 0.0)
    u = v_norm(v_cross(t, ref))
    v = v_norm(v_cross(t, u))
    return u, v


def add_static_ellipsoid(
    mesh: Mesh,
    center: Vec3,
    radii: Vec3,
    color: tuple[int, int, int],
    *,
    rings: int = 7,
    sides: int = 12,
) -> None:
    start = len(mesh.vertices)
    for ri in range(rings + 1):
        phi = math.pi * ri / rings
        yy = math.cos(phi)
        rr = math.sin(phi)
        for si in range(sides):
            theta = 2.0 * math.pi * si / sides
            p = (
                center[0] + radii[0] * rr * math.cos(theta),
                center[1] + radii[1] * yy,
                center[2] + radii[2] * rr * math.sin(theta),
            )
            mesh.vertices.append(Vertex(p, ()))
    for ri in range(rings):
        for si in range(sides):
            sj = (si + 1) % sides
            a = start + ri * sides + si
            b = start + (ri + 1) * sides + si
            c = start + (ri + 1) * sides + sj
            d = start + ri * sides + sj
            mesh.faces.append(Face(a, b, c, color))
            mesh.faces.append(Face(a, c, d, color))


def add_static_tube(
    mesh: Mesh,
    p0: Vec3,
    p1: Vec3,
    r0: float,
    r1: float,
    color: tuple[int, int, int],
    *,
    sides: int = 8,
) -> None:
    tangent = v_sub(p1, p0)
    u, v = _basis(tangent)
    rings: list[list[int]] = []
    for center, radius in ((p0, r0), (p1, r1)):
        ring: list[int] = []
        for si in range(sides):
            angle = 2.0 * math.pi * si / sides
            offset = v_add(
                v_scale(u, math.cos(angle) * radius),
                v_scale(v, math.sin(angle) * radius),
            )
            ring.append(len(mesh.vertices))
            mesh.vertices.append(Vertex(v_add(center, offset), ()))
        rings.append(ring)
    ra, rb = rings
    for i in range(sides):
        j = (i + 1) % sides
        mesh.faces.append(Face(ra[i], rb[i], rb[j], color))
        mesh.faces.append(Face(ra[i], rb[j], ra[j], color))


def add_static_quad(
    mesh: Mesh,
    a: Vec3,
    b: Vec3,
    c: Vec3,
    d: Vec3,
    color: tuple[int, int, int],
) -> None:
    start = len(mesh.vertices)
    for p in (a, b, c, d):
        mesh.vertices.append(Vertex(p, ()))
    mesh.faces.append(Face(start, start + 1, start + 2, color))
    mesh.faces.append(Face(start, start + 2, start + 3, color))


def build_dog_mesh(*, x: float = 0.0, y: float = -1.05) -> Mesh:
    """Create a recognizable stylized beagle-like quadruped from native geometry."""
    mesh = Mesh()
    brown = (145, 101, 70)
    dark = (76, 57, 48)
    tan = (190, 142, 98)
    cream = (226, 218, 198)
    black = (35, 32, 30)

    # Body and dark saddle.
    add_static_ellipsoid(mesh, (x, y, 0.0), (0.60, 0.30, 0.27), brown, rings=7, sides=12)
    add_static_ellipsoid(mesh, (x - 0.08, y + 0.08, -0.02), (0.44, 0.20, 0.28), dark, rings=6, sides=12)

    # Neck, head, muzzle and ears. Dog faces right in the default front view.
    add_static_tube(mesh, (x + 0.42, y + 0.06, 0.0), (x + 0.62, y + 0.28, 0.0), 0.18, 0.16, tan)
    add_static_ellipsoid(mesh, (x + 0.72, y + 0.32, 0.0), (0.28, 0.25, 0.24), tan, rings=6, sides=11)
    add_static_ellipsoid(mesh, (x + 0.96, y + 0.24, -0.01), (0.25, 0.15, 0.17), cream, rings=5, sides=10)
    add_static_ellipsoid(mesh, (x + 1.14, y + 0.25, -0.02), (0.065, 0.055, 0.06), black, rings=4, sides=8)
    add_static_ellipsoid(mesh, (x + 0.70, y + 0.38, -0.205), (0.035, 0.035, 0.025), black, rings=4, sides=7)
    add_static_ellipsoid(mesh, (x + 0.60, y + 0.20, -0.23), (0.12, 0.25, 0.055), dark, rings=5, sides=8)
    add_static_ellipsoid(mesh, (x + 0.60, y + 0.20, 0.23), (0.12, 0.25, 0.055), dark, rings=5, sides=8)

    # Four legs, slightly staggered in X so the silhouette is readable.
    leg_specs = (
        (x + 0.33, -0.16),
        (x + 0.48, 0.16),
        (x - 0.36, -0.16),
        (x - 0.20, 0.16),
    )
    for lx, lz in leg_specs:
        hip = (lx, y - 0.18, lz)
        ankle = (lx + (0.03 if lx > x else -0.03), -1.66, lz)
        paw = (ankle[0] + 0.08, -1.75, lz - 0.015)
        add_static_tube(mesh, hip, ankle, 0.095, 0.065, cream, sides=8)
        add_static_ellipsoid(mesh, paw, (0.13, 0.07, 0.10), cream, rings=4, sides=8)

    # Tail angled upward.
    add_static_tube(mesh, (x - 0.53, y + 0.08, 0.02), (x - 0.92, y + 0.38, 0.02), 0.075, 0.035, brown, sides=8)
    add_static_tube(mesh, (x - 0.92, y + 0.38, 0.02), (x - 1.10, y + 0.50, 0.02), 0.038, 0.018, cream, sides=8)
    mesh.validate()
    return mesh


def _translate_positions(points: Iterable[Vec3], offset: Vec3) -> list[Vec3]:
    return [v_add(p, offset) for p in points]


def _merge_meshes(meshes: Sequence[Mesh]) -> Mesh:
    out = Mesh()
    for mesh in meshes:
        base = len(out.vertices)
        out.vertices.extend(mesh.vertices)
        out.faces.extend(Face(f.a + base, f.b + base, f.c + base, f.color) for f in mesh.faces)
    out.validate()
    return out


def _natural_pose(text: str) -> Pose:
    pose = pose_from_prompt(text)
    rotations = dict(pose.rotations)
    arm_words = re.search(r"腕|手を上|手を振|arm|wave|waving|walk|歩", text, re.I)
    if not arm_words:
        rotations.setdefault("l_shoulder", (0.0, 0.0, -82.0))
        rotations.setdefault("r_shoulder", (0.0, 0.0, 82.0))
    return Pose(rotations)


def build_scene_geometry(plan: ScenePlan, prompt: str) -> tuple[Mesh, list[Vec3], tuple[str, ...], dict]:
    meshes: list[Mesh] = []
    position_blocks: list[list[Vec3]] = []
    generated: list[str] = []
    details: dict = {}

    has_human = "human" in plan.supported_objects
    has_dog = "dog" in plan.supported_objects

    if has_human:
        skeleton = default_human_skeleton()
        human = build_human_mesh(skeleton)
        pose = _natural_pose(prompt)
        human_points = skinned_positions(human, skeleton, pose)
        human_offset = (-0.62, 0.0, 0.0) if has_dog else (0.0, 0.0, 0.0)
        human_points = _translate_positions(human_points, human_offset)
        meshes.append(human)
        position_blocks.append(human_points)
        generated.append("human")
        details["human"] = {
            "bones": len(skeleton.bones),
            "pose_bones": sorted(pose.rotations),
            "offset": human_offset,
        }

    if has_dog:
        dog_x = 0.76 if has_human else 0.0
        dog = build_dog_mesh(x=dog_x)
        meshes.append(dog)
        position_blocks.append([v.bind_position for v in dog.vertices])
        generated.append("dog")
        details["dog"] = {
            "geometry": "native-quadruped-beagle-like",
            "offset_x": dog_x,
            "vertices": len(dog.vertices),
            "faces": len(dog.faces),
        }

    # If no supported semantic object is requested, still render a neutral ground.
    ground = Mesh()
    add_static_quad(
        ground,
        (-2.5, -1.84, -0.90),
        (2.5, -1.84, -0.90),
        (2.5, -1.84, 1.10),
        (-2.5, -1.84, 1.10),
        (204, 207, 203),
    )
    meshes.append(ground)
    position_blocks.append([v.bind_position for v in ground.vertices])

    merged = _merge_meshes(meshes)
    positions = [p for block in position_blocks for p in block]
    return merged, positions, tuple(generated), details


def _rotate_view(p: Vec3, yaw_deg: float, pitch_deg: float, center=(0.0, 0.10, 0.0)) -> Vec3:
    q = v_sub(p, center)
    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    x1 = cy * q[0] + sy * q[2]
    z1 = -sy * q[0] + cy * q[2]
    pitch = math.radians(pitch_deg)
    cp, sp = math.cos(pitch), math.sin(pitch)
    y2 = cp * q[1] - sp * z1
    z2 = sp * q[1] + cp * z1
    return (x1, y2, z2)


def _shade(color: tuple[int, int, int], intensity: float) -> tuple[int, int, int]:
    intensity = max(0.24, min(1.15, intensity))
    return tuple(max(0, min(255, int(c * intensity))) for c in color)


def _edge(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    return (px - ax) * (by - ay) - (py - ay) * (bx - ax)


def _paint_background(img: RGBImage) -> None:
    w, h = img.width, img.height
    for y in range(h):
        t = y / max(1, h - 1)
        top = (229, 235, 240)
        bottom = (245, 244, 238)
        color = tuple(int(top[i] * (1.0 - t) + bottom[i] * t) for i in range(3))
        row = bytes(color) * w
        start = y * w * 3
        img.data[start:start + w * 3] = row


def render_scene_png(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    width: int,
    height: int,
    yaw_deg: float = 0.0,
    pitch_deg: float = -4.0,
) -> bytes:
    if len(positions) != len(mesh.vertices):
        raise ValueError("positions must match mesh vertices")
    img = RGBImage(width, height)
    _paint_background(img)

    view = [_rotate_view(p, yaw_deg, pitch_deg) for p in positions]
    camera_distance = 7.0
    focal = min(width, height) * 1.40
    projected: list[tuple[float, float, float]] = []
    for x, y, z in view:
        zc = max(0.25, camera_distance + z)
        projected.append((
            width * 0.5 + focal * x / zc,
            height * 0.48 - focal * y / zc,
            zc,
        ))

    light = v_norm((-0.55, 0.82, -0.72))
    for face in mesh.faces:
        va, vb, vc = view[face.a], view[face.b], view[face.c]
        normal = v_norm(v_cross(v_sub(vb, va), v_sub(vc, va)))
        lambert = max(0.0, v_dot(normal, light))
        color = _shade(face.color, 0.40 + 0.72 * lambert)

        a, b, c = projected[face.a], projected[face.b], projected[face.c]
        area = _edge(a[0], a[1], b[0], b[1], c[0], c[1])
        if abs(area) < 1e-8:
            continue
        min_x = max(0, int(math.floor(min(a[0], b[0], c[0]))))
        max_x = min(width - 1, int(math.ceil(max(a[0], b[0], c[0]))))
        min_y = max(0, int(math.floor(min(a[1], b[1], c[1]))))
        max_y = min(height - 1, int(math.ceil(max(a[1], b[1], c[1]))))
        if min_x > max_x or min_y > max_y:
            continue
        inv_area = 1.0 / area
        for py in range(min_y, max_y + 1):
            fy = py + 0.5
            for px in range(min_x, max_x + 1):
                fx = px + 0.5
                w0 = _edge(b[0], b[1], c[0], c[1], fx, fy) * inv_area
                w1 = _edge(c[0], c[1], a[0], a[1], fx, fy) * inv_area
                w2 = 1.0 - w0 - w1
                if w0 < -1e-7 or w1 < -1e-7 or w2 < -1e-7:
                    continue
                z = w0 * a[2] + w1 * b[2] + w2 * c[2]
                img.set_depth(px, py, z, color)
    return img.png_bytes()


def requested_view(text: str) -> tuple[float, float]:
    return view_from_prompt(text)
