from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from fap_human_lbs.core import (
    Face,
    Mesh,
    RGBImage,
    v_add,
    v_cross,
    v_dot,
    v_len,
    v_norm,
    v_scale,
    v_sub,
)


Vec3 = tuple[float, float, float]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class MaterialProfile:
    ambient: float
    diffuse: float
    specular: float
    shininess: float
    micro_noise: float
    warm_shift: float = 0.0


def _is_near(color: Color, target: Color, tolerance: int = 34) -> bool:
    return sum(abs(int(a) - int(b)) for a, b in zip(color, target)) <= tolerance * 3


def _material(color: Color) -> MaterialProfile:
    # V87.30/V87.31 native palette-aware material approximation.
    if _is_near(color, (214, 171, 141), 32):  # skin
        return MaterialProfile(0.36, 0.72, 0.16, 22.0, 0.018, 0.018)
    if _is_near(color, (35, 32, 30), 28):  # glossy eyes/nose
        return MaterialProfile(0.26, 0.62, 0.48, 54.0, 0.010)
    if (
        _is_near(color, (145, 101, 70), 34)
        or _is_near(color, (76, 57, 48), 30)
        or _is_near(color, (190, 142, 98), 34)
        or _is_near(color, (226, 218, 198), 28)
    ):  # dog/fur
        return MaterialProfile(0.34, 0.76, 0.08, 12.0, 0.060, 0.012)
    if _is_near(color, (71, 112, 158), 36):  # shirt
        return MaterialProfile(0.31, 0.72, 0.05, 9.0, 0.040)
    if _is_near(color, (57, 66, 82), 34):  # trousers
        return MaterialProfile(0.29, 0.68, 0.035, 8.0, 0.035)
    if _is_near(color, (52, 48, 45), 30):  # shoes
        return MaterialProfile(0.24, 0.62, 0.18, 26.0, 0.025)
    return MaterialProfile(0.34, 0.70, 0.08, 14.0, 0.018)


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


def _edge(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    return (px - ax) * (by - ay) - (py - ay) * (bx - ax)


def _clamp8(v: float) -> int:
    return max(0, min(255, int(v + 0.5)))


def _noise01(x: int, y: int, seed: int) -> float:
    # Stable integer hash; avoids random module overhead in the inner raster loop.
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFF) / 65535.0


def _paint_studio_background(img: RGBImage) -> None:
    w, h = img.width, img.height
    horizon = int(h * 0.69)
    for y in range(h):
        if y < horizon:
            t = y / max(1, horizon - 1)
            top = (220, 229, 236)
            bottom = (243, 242, 237)
            color = tuple(int(top[i] * (1.0 - t) + bottom[i] * t) for i in range(3))
        else:
            t = (y - horizon) / max(1, h - horizon - 1)
            top = (224, 220, 211)
            bottom = (196, 191, 181)
            color = tuple(int(top[i] * (1.0 - t) + bottom[i] * t) for i in range(3))

        # Broad studio-light hotspot, kept cheap by doing one scalar per scanline.
        row = bytearray()
        for x in range(w):
            dx = (x - w * 0.49) / max(1.0, w * 0.58)
            dy = (y - h * 0.34) / max(1.0, h * 0.72)
            glow = max(0.0, 1.0 - (dx * dx + dy * dy)) * 5.0
            row.extend((_clamp8(color[0] + glow), _clamp8(color[1] + glow), _clamp8(color[2] + glow)))
        start = y * w * 3
        img.data[start:start + w * 3] = row


def _project(p: Vec3, *, width: int, height: int, yaw_deg: float, pitch_deg: float) -> tuple[float, float, float]:
    x, y, z = _rotate_view(p, yaw_deg, pitch_deg)
    camera_distance = 7.0
    focal = min(width, height) * 1.40
    zc = max(0.25, camera_distance + z)
    return (
        width * 0.5 + focal * x / zc,
        height * 0.48 - focal * y / zc,
        zc,
    )


def _soft_ellipse(
    img: RGBImage,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    opacity: float,
    tint: Color = (58, 53, 48),
) -> None:
    if rx <= 1.0 or ry <= 1.0:
        return
    x0 = max(0, int(cx - rx))
    x1 = min(img.width - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(img.height - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        ny = (y + 0.5 - cy) / ry
        ny2 = ny * ny
        if ny2 >= 1.0:
            continue
        for x in range(x0, x1 + 1):
            nx = (x + 0.5 - cx) / rx
            r2 = nx * nx + ny2
            if r2 >= 1.0:
                continue
            falloff = (1.0 - r2)
            alpha = opacity * falloff * falloff
            off = (y * img.width + x) * 3
            for k in range(3):
                base = img.data[off + k]
                img.data[off + k] = _clamp8(base * (1.0 - alpha) + tint[k] * alpha)


def _accumulate_vertex_normals(mesh: Mesh, view: Sequence[Vec3]) -> list[Vec3]:
    sums = [[0.0, 0.0, 0.0] for _ in mesh.vertices]
    for face in mesh.faces:
        # Ground plane is studio background in V87.32; it does not contribute
        # to subject smooth normals.
        if face.color == (204, 207, 203):
            continue
        a, b, c = view[face.a], view[face.b], view[face.c]
        cross = v_cross(v_sub(b, a), v_sub(c, a))
        if v_len(cross) <= 1e-12:
            continue
        for idx in (face.a, face.b, face.c):
            sums[idx][0] += cross[0]
            sums[idx][1] += cross[1]
            sums[idx][2] += cross[2]
    return [v_norm((x, y, z)) for x, y, z in sums]


def _subject_shadows(
    img: RGBImage,
    generated_objects: Sequence[str],
    *,
    yaw_deg: float,
    pitch_deg: float,
) -> None:
    specs = []
    objects = set(generated_objects)
    if "human" in objects:
        hx = -0.62 if "dog" in objects else 0.0
        specs.append(((hx, -1.80, 0.02), 0.44, 0.115, 0.30))
    if "dog" in objects:
        dx = 0.76 if "human" in objects else 0.0
        specs.append(((dx, -1.78, 0.02), 0.78, 0.135, 0.34))

    for center, world_rx, vertical_ratio, opacity in specs:
        sx, sy, zc = _project(
            center,
            width=img.width,
            height=img.height,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
        )
        focal = min(img.width, img.height) * 1.40
        rx = focal * world_rx / zc
        ry = max(3.0, rx * vertical_ratio)
        _soft_ellipse(img, sx, sy + ry * 0.25, rx, ry, opacity=opacity)


def _render_subject_faces(
    img: RGBImage,
    mesh: Mesh,
    view: Sequence[Vec3],
    projected: Sequence[tuple[float, float, float]],
    vertex_normals: Sequence[Vec3],
) -> None:
    light = v_norm((-0.48, 0.78, -0.72))
    fill = v_norm((0.66, 0.38, -0.34))
    view_dir = (0.0, 0.0, -1.0)

    for face_index, face in enumerate(mesh.faces):
        if face.color == (204, 207, 203):
            continue

        a, b, c = projected[face.a], projected[face.b], projected[face.c]
        area = _edge(a[0], a[1], b[0], b[1], c[0], c[1])
        if abs(area) < 1e-8:
            continue

        min_x = max(0, int(math.floor(min(a[0], b[0], c[0]))))
        max_x = min(img.width - 1, int(math.ceil(max(a[0], b[0], c[0]))))
        min_y = max(0, int(math.floor(min(a[1], b[1], c[1]))))
        max_y = min(img.height - 1, int(math.ceil(max(a[1], b[1], c[1]))))
        if min_x > max_x or min_y > max_y:
            continue

        inv_area = 1.0 / area
        na, nb, nc = vertex_normals[face.a], vertex_normals[face.b], vertex_normals[face.c]
        mat = _material(face.color)
        half_vec = v_norm(v_add(light, view_dir))

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
                idx = py * img.width + px
                if z >= img.depth[idx]:
                    continue

                n = v_norm((
                    na[0] * w0 + nb[0] * w1 + nc[0] * w2,
                    na[1] * w0 + nb[1] * w1 + nc[1] * w2,
                    na[2] * w0 + nb[2] * w1 + nc[2] * w2,
                ))
                if v_dot(n, view_dir) < 0.0:
                    n = (-n[0], -n[1], -n[2])

                ndl = v_dot(n, light)
                wrapped = max(0.0, min(1.0, (ndl + 0.24) / 1.24))
                fill_term = max(0.0, v_dot(n, fill))
                spec = max(0.0, v_dot(n, half_vec)) ** mat.shininess
                rim = max(0.0, 1.0 - max(0.0, v_dot(n, view_dir))) ** 2

                illumination = (
                    mat.ambient
                    + mat.diffuse * wrapped
                    + 0.10 * fill_term
                    + 0.035 * rim
                )
                micro = (_noise01(px, py, face_index + 17) - 0.5) * 2.0 * mat.micro_noise
                illumination *= 1.0 + micro

                warm = mat.warm_shift * (0.6 + 0.4 * wrapped)
                base = face.color
                out = [
                    base[0] * illumination * (1.0 + warm),
                    base[1] * illumination,
                    base[2] * illumination * (1.0 - warm * 0.55),
                ]
                highlight = 255.0 * mat.specular * spec
                out = [_clamp8(v + highlight) for v in out]

                img.depth[idx] = z
                off = idx * 3
                img.data[off:off + 3] = bytes(out)


def _fxaa_pass(img: RGBImage) -> None:
    w, h = img.width, img.height
    if w < 3 or h < 3:
        return
    src = bytes(img.data)

    def luma(off: int) -> float:
        return 0.2126 * src[off] + 0.7152 * src[off + 1] + 0.0722 * src[off + 2]

    for y in range(1, h - 1):
        for x in range(1, w - 1):
            off = (y * w + x) * 3
            offsets = (
                off,
                off - 3,
                off + 3,
                off - w * 3,
                off + w * 3,
            )
            lum = [luma(q) for q in offsets]
            contrast = max(lum) - min(lum)
            if contrast < 34.0:
                continue
            for k in range(3):
                center = src[off + k]
                neighbor = (
                    src[offsets[1] + k]
                    + src[offsets[2] + k]
                    + src[offsets[3] + k]
                    + src[offsets[4] + k]
                ) * 0.25
                img.data[off + k] = _clamp8(center * 0.62 + neighbor * 0.38)


def _filmic_finish(img: RGBImage) -> None:
    w, h = img.width, img.height
    cx, cy = (w - 1) * 0.5, (h - 1) * 0.48
    invx = 1.0 / max(1.0, w * 0.72)
    invy = 1.0 / max(1.0, h * 0.78)
    for y in range(h):
        dy = (y - cy) * invy
        for x in range(w):
            dx = (x - cx) * invx
            r2 = dx * dx + dy * dy
            vignette = max(0.84, 1.0 - 0.12 * r2)
            off = (y * w + x) * 3
            grain = (_noise01(x, y, 991) - 0.5) * 2.2
            vals = []
            for k in range(3):
                v = img.data[off + k] / 255.0
                # Gentle toe/shoulder curve followed by a small gamma lift.
                v = max(0.0, min(1.0, (v * 1.055) / (1.0 + 0.055 * v)))
                v = v ** 0.94
                vals.append(_clamp8(v * 255.0 * vignette + grain))
            img.data[off:off + 3] = bytes(vals)


def render_photo_look_png(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float = 0.0,
    pitch_deg: float = -4.0,
) -> tuple[bytes, dict]:
    if len(positions) != len(mesh.vertices):
        raise ValueError("positions must match mesh vertices")
    if width < 64 or height < 64:
        raise ValueError("render dimensions too small")

    img = RGBImage(width, height)
    _paint_studio_background(img)

    view = [_rotate_view(p, yaw_deg, pitch_deg) for p in positions]
    projected = [
        _project(
            p,
            width=width,
            height=height,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
        )
        for p in positions
    ]
    normals = _accumulate_vertex_normals(mesh, view)

    # Studio ground is painted in the background; explicit ground triangles are
    # intentionally skipped to avoid the flat polygonal slab from V87.31.
    _subject_shadows(
        img,
        generated_objects,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
    )
    _render_subject_faces(img, mesh, view, projected, normals)
    _fxaa_pass(img)
    _filmic_finish(img)

    return img.png_bytes(), {
        "smooth_vertex_normals": True,
        "material_profiles": True,
        "micro_surface_variation": True,
        "contact_shadows": True,
        "studio_background": True,
        "fxaa": True,
        "filmic_finish": True,
        "learned_refiner": False,
    }
