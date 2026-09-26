from __future__ import annotations

from dataclasses import dataclass, field
import math
import struct
import zlib
from typing import Iterable, Mapping, Sequence


Vec3 = tuple[float, float, float]
Mat4 = tuple[float, ...]
Weights = tuple[tuple[str, float], ...]


def v_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def v_len(a: Vec3) -> float:
    return math.sqrt(max(0.0, v_dot(a, a)))


def v_norm(a: Vec3) -> Vec3:
    n = v_len(a)
    if n <= 1e-12:
        return (0.0, 1.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def mat_identity() -> Mat4:
    return (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )


def mat_mul(a: Mat4, b: Mat4) -> Mat4:
    out = [0.0] * 16
    for r in range(4):
        for c in range(4):
            out[r * 4 + c] = sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
    return tuple(out)


def mat_translate(v: Vec3) -> Mat4:
    x, y, z = v
    return (
        1.0, 0.0, 0.0, x,
        0.0, 1.0, 0.0, y,
        0.0, 0.0, 1.0, z,
        0.0, 0.0, 0.0, 1.0,
    )


def mat_rot_x(rad: float) -> Mat4:
    c, s = math.cos(rad), math.sin(rad)
    return (
        1.0, 0.0, 0.0, 0.0,
        0.0, c, -s, 0.0,
        0.0, s, c, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )


def mat_rot_y(rad: float) -> Mat4:
    c, s = math.cos(rad), math.sin(rad)
    return (
        c, 0.0, s, 0.0,
        0.0, 1.0, 0.0, 0.0,
        -s, 0.0, c, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )


def mat_rot_z(rad: float) -> Mat4:
    c, s = math.cos(rad), math.sin(rad)
    return (
        c, -s, 0.0, 0.0,
        s, c, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )


def mat_euler_deg(xyz: Vec3) -> Mat4:
    rx, ry, rz = (math.radians(float(v)) for v in xyz)
    return mat_mul(mat_mul(mat_rot_z(rz), mat_rot_y(ry)), mat_rot_x(rx))


def mat_point(m: Mat4, p: Vec3) -> Vec3:
    x, y, z = p
    return (
        m[0] * x + m[1] * y + m[2] * z + m[3],
        m[4] * x + m[5] * y + m[6] * z + m[7],
        m[8] * x + m[9] * y + m[10] * z + m[11],
    )


def mat_rigid_inverse(m: Mat4) -> Mat4:
    r00, r01, r02 = m[0], m[1], m[2]
    r10, r11, r12 = m[4], m[5], m[6]
    r20, r21, r22 = m[8], m[9], m[10]
    tx, ty, tz = m[3], m[7], m[11]
    itx = -(r00 * tx + r10 * ty + r20 * tz)
    ity = -(r01 * tx + r11 * ty + r21 * tz)
    itz = -(r02 * tx + r12 * ty + r22 * tz)
    return (
        r00, r10, r20, itx,
        r01, r11, r21, ity,
        r02, r12, r22, itz,
        0.0, 0.0, 0.0, 1.0,
    )


@dataclass(frozen=True)
class Bone:
    name: str
    parent: str | None
    offset: Vec3
    limit_min: Vec3 = (-180.0, -180.0, -180.0)
    limit_max: Vec3 = (180.0, 180.0, 180.0)


@dataclass
class Pose:
    rotations: dict[str, Vec3] = field(default_factory=dict)

    def rotation(self, bone: str) -> Vec3:
        return self.rotations.get(bone, (0.0, 0.0, 0.0))


class Skeleton:
    def __init__(self, bones: Sequence[Bone]):
        self.bones = tuple(bones)
        self.by_name = {b.name: b for b in bones}
        if len(self.by_name) != len(self.bones):
            raise ValueError("duplicate bone name")
        seen: set[str] = set()
        for bone in self.bones:
            if bone.parent is not None and bone.parent not in seen:
                raise ValueError(f"parent must precede child: {bone.name}")
            seen.add(bone.name)
        self._bind_globals = self.global_matrices(Pose())
        self._inverse_bind = {
            name: mat_rigid_inverse(matrix)
            for name, matrix in self._bind_globals.items()
        }

    def clamp_pose(self, pose: Pose) -> Pose:
        out: dict[str, Vec3] = {}
        for name, rot in pose.rotations.items():
            bone = self.by_name.get(name)
            if bone is None:
                continue
            out[name] = tuple(
                max(bone.limit_min[i], min(bone.limit_max[i], float(rot[i])))
                for i in range(3)
            )
        return Pose(out)

    def global_matrices(self, pose: Pose) -> dict[str, Mat4]:
        pose = self.clamp_pose(pose)
        out: dict[str, Mat4] = {}
        for bone in self.bones:
            local = mat_mul(mat_translate(bone.offset), mat_euler_deg(pose.rotation(bone.name)))
            out[bone.name] = local if bone.parent is None else mat_mul(out[bone.parent], local)
        return out

    def bind_joint(self, name: str) -> Vec3:
        return mat_point(self._bind_globals[name], (0.0, 0.0, 0.0))

    def posed_joint(self, name: str, pose: Pose) -> Vec3:
        return mat_point(self.global_matrices(pose)[name], (0.0, 0.0, 0.0))

    def skin_point(self, bind_point: Vec3, weights: Weights, pose: Pose) -> Vec3:
        globals_now = self.global_matrices(pose)
        return self.skin_point_with_globals(bind_point, weights, globals_now)

    def skin_point_with_globals(
        self,
        bind_point: Vec3,
        weights: Weights,
        pose_globals: Mapping[str, Mat4],
    ) -> Vec3:
        if not weights:
            return bind_point
        total = sum(max(0.0, float(w)) for _, w in weights)
        if total <= 1e-12:
            return bind_point
        result = (0.0, 0.0, 0.0)
        for bone_name, raw_weight in weights:
            weight = max(0.0, float(raw_weight)) / total
            local = mat_point(self._inverse_bind[bone_name], bind_point)
            posed = mat_point(pose_globals[bone_name], local)
            result = v_add(result, v_scale(posed, weight))
        return result


@dataclass(frozen=True)
class Vertex:
    bind_position: Vec3
    weights: Weights


@dataclass(frozen=True)
class Face:
    a: int
    b: int
    c: int
    color: tuple[int, int, int]


@dataclass
class Mesh:
    vertices: list[Vertex] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)

    def validate(self) -> None:
        if not self.vertices or not self.faces:
            raise ValueError("mesh is empty")
        for vertex in self.vertices:
            total = sum(w for _, w in vertex.weights)
            if vertex.weights and abs(total - 1.0) > 1e-6:
                raise ValueError("vertex weights must sum to 1")
            if len(vertex.weights) > 4:
                raise ValueError("too many bone influences")
        n = len(self.vertices)
        for face in self.faces:
            if not (0 <= face.a < n and 0 <= face.b < n and 0 <= face.c < n):
                raise ValueError("face index out of bounds")


def default_human_skeleton() -> Skeleton:
    B = Bone
    bones = [
        B("pelvis", None, (0.0, 0.0, 0.0), (-35, -45, -35), (35, 45, 35)),
        B("spine", "pelvis", (0.0, 0.55, 0.0), (-35, -35, -30), (35, 35, 30)),
        B("chest", "spine", (0.0, 0.62, 0.0), (-35, -45, -35), (35, 45, 35)),
        B("neck", "chest", (0.0, 0.43, 0.0), (-45, -55, -45), (45, 55, 45)),
        B("head", "neck", (0.0, 0.38, 0.0), (-45, -60, -45), (45, 60, 45)),
        B("l_shoulder", "chest", (0.44, 0.12, 0.0), (-130, -120, -130), (130, 120, 130)),
        B("l_elbow", "l_shoulder", (0.62, 0.0, 0.0), (-20, -20, -145), (20, 20, 145)),
        B("l_wrist", "l_elbow", (0.54, 0.0, 0.0), (-60, -60, -70), (60, 60, 70)),
        B("l_hand", "l_wrist", (0.22, 0.0, 0.0), (-45, -45, -45), (45, 45, 45)),
        B("r_shoulder", "chest", (-0.44, 0.12, 0.0), (-130, -120, -130), (130, 120, 130)),
        B("r_elbow", "r_shoulder", (-0.62, 0.0, 0.0), (-20, -20, -145), (20, 20, 145)),
        B("r_wrist", "r_elbow", (-0.54, 0.0, 0.0), (-60, -60, -70), (60, 60, 70)),
        B("r_hand", "r_wrist", (-0.22, 0.0, 0.0), (-45, -45, -45), (45, 45, 45)),
        B("l_hip", "pelvis", (0.25, -0.13, 0.0), (-120, -55, -45), (120, 55, 45)),
        B("l_knee", "l_hip", (0.0, -0.82, 0.0), (-145, -15, -15), (15, 15, 15)),
        B("l_ankle", "l_knee", (0.0, -0.78, 0.0), (-55, -35, -35), (55, 35, 35)),
        B("l_foot", "l_ankle", (0.0, -0.08, 0.28), (-35, -30, -25), (35, 30, 25)),
        B("r_hip", "pelvis", (-0.25, -0.13, 0.0), (-120, -55, -45), (120, 55, 45)),
        B("r_knee", "r_hip", (0.0, -0.82, 0.0), (-145, -15, -15), (15, 15, 15)),
        B("r_ankle", "r_knee", (0.0, -0.78, 0.0), (-55, -35, -35), (55, 35, 35)),
        B("r_foot", "r_ankle", (0.0, -0.08, 0.28), (-35, -30, -25), (35, 30, 25)),
    ]
    return Skeleton(bones)


def _ring_basis(tangent: Vec3) -> tuple[Vec3, Vec3]:
    t = v_norm(tangent)
    ref = (0.0, 0.0, 1.0)
    if abs(v_dot(t, ref)) > 0.93:
        ref = (1.0, 0.0, 0.0)
    u = v_norm(v_cross(t, ref))
    v = v_norm(v_cross(t, u))
    return u, v


def _blend_weights(a: str, b: str | None, t: float) -> Weights:
    if b is None or t <= 1e-9:
        return ((a, 1.0),)
    if t >= 1.0 - 1e-9:
        return ((b, 1.0),)
    return ((a, 1.0 - t), (b, t))


def add_chain_surface(
    mesh: Mesh,
    points: Sequence[Vec3],
    bones: Sequence[str],
    radii: Sequence[float | tuple[float, float]],
    color: tuple[int, int, int],
    *,
    sides: int = 10,
    subdivisions: int = 2,
) -> None:
    if not (len(points) == len(bones) == len(radii)):
        raise ValueError("chain arrays must match")
    if len(points) < 2:
        raise ValueError("chain needs two points")
    samples: list[tuple[Vec3, Weights, tuple[float, float], Vec3]] = []
    for seg in range(len(points) - 1):
        p0, p1 = points[seg], points[seg + 1]
        tangent = v_sub(p1, p0)
        r0 = radii[seg] if isinstance(radii[seg], tuple) else (float(radii[seg]), float(radii[seg]))
        r1 = radii[seg + 1] if isinstance(radii[seg + 1], tuple) else (float(radii[seg + 1]), float(radii[seg + 1]))
        for step in range(subdivisions + 1):
            if seg > 0 and step == 0:
                continue
            t = step / subdivisions
            p = v_add(p0, v_scale(tangent, t))
            rx = r0[0] + (r1[0] - r0[0]) * t
            ry = r0[1] + (r1[1] - r0[1]) * t
            if step == subdivisions and seg < len(points) - 2:
                weights = ((bones[seg], 0.5), (bones[seg + 1], 0.5))
            elif seg == len(points) - 2 and step == subdivisions:
                weights = ((bones[seg + 1], 1.0),)
            else:
                blend = max(0.0, (t - 0.65) / 0.35)
                weights = _blend_weights(bones[seg], bones[seg + 1], blend)
            samples.append((p, weights, (rx, ry), tangent))

    rings: list[list[int]] = []
    for idx, (center, weights, radius, tangent) in enumerate(samples):
        if 0 < idx < len(samples) - 1:
            tangent = v_sub(samples[idx + 1][0], samples[idx - 1][0])
        u, v = _ring_basis(tangent)
        ring: list[int] = []
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides
            offset = v_add(
                v_scale(u, math.cos(angle) * radius[0]),
                v_scale(v, math.sin(angle) * radius[1]),
            )
            ring.append(len(mesh.vertices))
            mesh.vertices.append(Vertex(v_add(center, offset), weights))
        rings.append(ring)

    for ra, rb in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            mesh.faces.append(Face(ra[i], rb[i], rb[j], color))
            mesh.faces.append(Face(ra[i], rb[j], ra[j], color))


def add_ellipsoid(
    mesh: Mesh,
    center: Vec3,
    radii: Vec3,
    bone: str,
    color: tuple[int, int, int],
    *,
    rings: int = 7,
    sides: int = 12,
) -> None:
    start = len(mesh.vertices)
    for ri in range(rings + 1):
        phi = math.pi * ri / rings
        y = math.cos(phi)
        rr = math.sin(phi)
        for si in range(sides):
            theta = 2.0 * math.pi * si / sides
            p = (
                center[0] + radii[0] * rr * math.cos(theta),
                center[1] + radii[1] * y,
                center[2] + radii[2] * rr * math.sin(theta),
            )
            mesh.vertices.append(Vertex(p, ((bone, 1.0),)))
    for ri in range(rings):
        for si in range(sides):
            sj = (si + 1) % sides
            a = start + ri * sides + si
            b = start + (ri + 1) * sides + si
            c = start + (ri + 1) * sides + sj
            d = start + ri * sides + sj
            mesh.faces.append(Face(a, b, c, color))
            mesh.faces.append(Face(a, c, d, color))


def build_human_mesh(skeleton: Skeleton | None = None) -> Mesh:
    sk = skeleton or default_human_skeleton()
    j = sk.bind_joint
    mesh = Mesh()
    skin = (214, 171, 141)
    shirt = (71, 112, 158)
    trousers = (57, 66, 82)
    shoe = (52, 48, 45)

    add_chain_surface(
        mesh,
        [j("pelvis"), j("spine"), j("chest"), j("neck")],
        ["pelvis", "spine", "chest", "neck"],
        [(0.34, 0.22), (0.39, 0.24), (0.48, 0.27), (0.18, 0.16)],
        shirt,
        sides=12,
        subdivisions=2,
    )
    add_chain_surface(
        mesh,
        [j("l_shoulder"), j("l_elbow"), j("l_wrist"), j("l_hand")],
        ["l_shoulder", "l_elbow", "l_wrist", "l_hand"],
        [0.17, 0.145, 0.11, 0.10],
        skin,
        sides=9,
        subdivisions=2,
    )
    add_chain_surface(
        mesh,
        [j("r_shoulder"), j("r_elbow"), j("r_wrist"), j("r_hand")],
        ["r_shoulder", "r_elbow", "r_wrist", "r_hand"],
        [0.17, 0.145, 0.11, 0.10],
        skin,
        sides=9,
        subdivisions=2,
    )
    add_chain_surface(
        mesh,
        [j("l_hip"), j("l_knee"), j("l_ankle"), j("l_foot")],
        ["l_hip", "l_knee", "l_ankle", "l_foot"],
        [0.24, 0.19, 0.12, 0.13],
        trousers,
        sides=10,
        subdivisions=2,
    )
    add_chain_surface(
        mesh,
        [j("r_hip"), j("r_knee"), j("r_ankle"), j("r_foot")],
        ["r_hip", "r_knee", "r_ankle", "r_foot"],
        [0.24, 0.19, 0.12, 0.13],
        trousers,
        sides=10,
        subdivisions=2,
    )
    add_ellipsoid(mesh, j("head"), (0.25, 0.31, 0.23), "head", skin, rings=7, sides=12)
    add_ellipsoid(mesh, j("l_hand"), (0.13, 0.09, 0.08), "l_hand", skin, rings=5, sides=8)
    add_ellipsoid(mesh, j("r_hand"), (0.13, 0.09, 0.08), "r_hand", skin, rings=5, sides=8)

    lf = v_add(j("l_foot"), (0.0, -0.03, 0.10))
    rf = v_add(j("r_foot"), (0.0, -0.03, 0.10))
    add_ellipsoid(mesh, lf, (0.15, 0.09, 0.24), "l_foot", shoe, rings=5, sides=8)
    add_ellipsoid(mesh, rf, (0.15, 0.09, 0.24), "r_foot", shoe, rings=5, sides=8)
    mesh.validate()
    return mesh


def skinned_positions(mesh: Mesh, skeleton: Skeleton, pose: Pose) -> list[Vec3]:
    globals_now = skeleton.global_matrices(pose)
    return [
        skeleton.skin_point_with_globals(v.bind_position, v.weights, globals_now)
        for v in mesh.vertices
    ]


class RGBImage:
    def __init__(self, width: int, height: int, background=(238, 241, 245)):
        self.width = int(width)
        self.height = int(height)
        self.data = bytearray(bytes(background) * (self.width * self.height))
        self.depth = [float("inf")] * (self.width * self.height)

    def set_depth(self, x: int, y: int, z: float, color: tuple[int, int, int]) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        idx = y * self.width + x
        if z >= self.depth[idx]:
            return
        self.depth[idx] = z
        off = idx * 3
        self.data[off:off + 3] = bytes(color)

    def png_bytes(self) -> bytes:
        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (
                struct.pack(">I", len(payload))
                + tag
                + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
            )

        stride = self.width * 3
        raw = bytearray()
        for y in range(self.height):
            raw.append(0)
            start = y * stride
            raw.extend(self.data[start:start + stride])
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b"")
        )


def _rotate_view(p: Vec3, yaw_deg: float, pitch_deg: float, center=(0.0, 0.15, 0.0)) -> Vec3:
    q = v_sub(p, center)
    y = math.radians(yaw_deg)
    cy, sy = math.cos(y), math.sin(y)
    x1 = cy * q[0] + sy * q[2]
    z1 = -sy * q[0] + cy * q[2]
    pch = math.radians(pitch_deg)
    cp, sp = math.cos(pch), math.sin(pch)
    y2 = cp * q[1] - sp * z1
    z2 = sp * q[1] + cp * z1
    return (x1, y2, z2)


def _shade(color: tuple[int, int, int], intensity: float) -> tuple[int, int, int]:
    intensity = max(0.20, min(1.15, intensity))
    return tuple(max(0, min(255, int(c * intensity))) for c in color)


def _edge(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    return (px - ax) * (by - ay) - (py - ay) * (bx - ax)


def render_human_png(
    mesh: Mesh,
    skeleton: Skeleton,
    pose: Pose,
    *,
    width: int = 512,
    height: int = 640,
    yaw_deg: float = 0.0,
    pitch_deg: float = -3.0,
) -> bytes:
    if width < 64 or height < 64:
        raise ValueError("render dimensions too small")
    img = RGBImage(width, height)
    positions = skinned_positions(mesh, skeleton, pose)
    view = [_rotate_view(p, yaw_deg, pitch_deg) for p in positions]
    camera_distance = 6.6
    focal = min(width, height) * 1.62

    projected: list[tuple[float, float, float]] = []
    for x, y, z in view:
        zc = camera_distance + z
        zc = max(0.2, zc)
        sx = width * 0.5 + focal * x / zc
        sy = height * 0.50 - focal * y / zc
        projected.append((sx, sy, zc))

    light = v_norm((-0.45, 0.75, -0.65))
    for face in mesh.faces:
        ia, ib, ic = face.a, face.b, face.c
        va, vb, vc = view[ia], view[ib], view[ic]
        normal = v_norm(v_cross(v_sub(vb, va), v_sub(vc, va)))
        lambert = max(0.0, v_dot(normal, light))
        color = _shade(face.color, 0.42 + 0.68 * lambert)

        a, b, c = projected[ia], projected[ib], projected[ic]
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


def view_from_prompt(text: str) -> tuple[float, float]:
    low = text.lower()
    if any(k in low for k in ("side view", "profile", "側面", "横向き")):
        return (88.0, -3.0)
    if any(k in low for k in ("back view", "背面", "後ろ")):
        return (178.0, -3.0)
    if any(k in low for k in ("oblique", "three-quarter", "3/4", "斜め")):
        return (35.0, -5.0)
    return (0.0, -3.0)


def pose_from_prompt(text: str) -> Pose:
    low = text.lower()
    r: dict[str, Vec3] = {}

    def has(*terms: str) -> bool:
        return any(term.lower() in low for term in terms)

    if has("arms down", "腕を下", "腕をおろ", "直立"):
        r["l_shoulder"] = (0.0, 0.0, -82.0)
        r["r_shoulder"] = (0.0, 0.0, 82.0)
    if has("raise left arm", "left arm up", "左腕を上", "左手を上"):
        r["l_shoulder"] = (0.0, 0.0, 88.0)
    if has("raise right arm", "right arm up", "右腕を上", "右手を上"):
        r["r_shoulder"] = (0.0, 0.0, -88.0)
    if has("both arms up", "両腕を上", "両手を上"):
        r["l_shoulder"] = (0.0, 0.0, 88.0)
        r["r_shoulder"] = (0.0, 0.0, -88.0)
    if has("bend left elbow", "左肘", "左ひじ"):
        r["l_elbow"] = (0.0, 0.0, 72.0)
    if has("bend right elbow", "右肘", "右ひじ"):
        r["r_elbow"] = (0.0, 0.0, -72.0)
    if has("wave", "手を振", "waving"):
        r["r_shoulder"] = (0.0, 0.0, -82.0)
        r["r_elbow"] = (0.0, 0.0, -82.0)
        r["r_wrist"] = (0.0, 0.0, 28.0)
    if has("walk", "walking", "歩く", "歩行"):
        r["l_hip"] = (24.0, 0.0, 0.0)
        r["r_hip"] = (-22.0, 0.0, 0.0)
        r["l_knee"] = (-18.0, 0.0, 0.0)
        r["r_knee"] = (-45.0, 0.0, 0.0)
        r["l_shoulder"] = (-18.0, 0.0, -8.0)
        r["r_shoulder"] = (18.0, 0.0, 8.0)
    if has("sit", "sitting", "座る", "座った"):
        r["l_hip"] = (-82.0, 0.0, 0.0)
        r["r_hip"] = (-82.0, 0.0, 0.0)
        r["l_knee"] = (-92.0, 0.0, 0.0)
        r["r_knee"] = (-92.0, 0.0, 0.0)
    if has("look left", "左を見る"):
        r["neck"] = (0.0, 30.0, 0.0)
        r["head"] = (0.0, 18.0, 0.0)
    if has("look right", "右を見る"):
        r["neck"] = (0.0, -30.0, 0.0)
        r["head"] = (0.0, -18.0, 0.0)
    return Pose(r)
