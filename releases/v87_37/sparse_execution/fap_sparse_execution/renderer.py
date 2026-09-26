from __future__ import annotations

from functools import lru_cache
import math
import threading
from typing import Sequence

from fap_human_lbs.core import Mesh, RGBImage
from fap_photo_look import renderer as dense


Vec3 = tuple[float, float, float]
_THREAD_STATE = threading.local()


def last_render_stats() -> dict:
    return dict(getattr(_THREAD_STATE, "last_stats", {}) or {})


def _remember_stats(stats: dict) -> None:
    _THREAD_STATE.last_stats = dict(stats)


def _tile_bounds(tile_x: int, tile_y: int, tile_size: int, width: int, height: int):
    x0 = tile_x * tile_size
    y0 = tile_y * tile_size
    return (
        x0,
        y0,
        min(width, x0 + tile_size),
        min(height, y0 + tile_size),
    )


def _active_tiles(
    mesh: Mesh,
    projected: Sequence[tuple[float, float, float]],
    *,
    width: int,
    height: int,
    tile_size: int,
    pad: int = 2,
) -> set[tuple[int, int]]:
    tiles: set[tuple[int, int]] = set()
    max_tx = max(0, (width - 1) // tile_size)
    max_ty = max(0, (height - 1) // tile_size)
    for face in mesh.faces:
        if face.color == (204, 207, 203):
            continue
        a, b, c = projected[face.a], projected[face.b], projected[face.c]
        min_x = max(0, int(math.floor(min(a[0], b[0], c[0]))) - pad)
        max_x = min(width - 1, int(math.ceil(max(a[0], b[0], c[0]))) + pad)
        min_y = max(0, int(math.floor(min(a[1], b[1], c[1]))) - pad)
        max_y = min(height - 1, int(math.ceil(max(a[1], b[1], c[1]))) + pad)
        if min_x > max_x or min_y > max_y:
            continue
        for ty in range(min_y // tile_size, max_y // tile_size + 1):
            for tx in range(min_x // tile_size, max_x // tile_size + 1):
                if 0 <= tx <= max_tx and 0 <= ty <= max_ty:
                    tiles.add((tx, ty))
    return tiles


@lru_cache(maxsize=8)
def _finished_background(width: int, height: int) -> bytes:
    img = RGBImage(width, height)
    dense._paint_studio_background(img)
    dense._filmic_finish(img)
    return bytes(img.data)


def background_cache_info() -> dict:
    info = _finished_background.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "currsize": info.currsize,
        "maxsize": info.maxsize,
    }


def _fxaa_tiles(img: RGBImage, tiles: set[tuple[int, int]], tile_size: int) -> int:
    w, h = img.width, img.height
    if w < 3 or h < 3 or not tiles:
        return 0
    src = bytes(img.data)

    def luma(off: int) -> float:
        return 0.2126 * src[off] + 0.7152 * src[off + 1] + 0.0722 * src[off + 2]

    touched = 0
    for tx, ty in sorted(tiles):
        x0, y0, x1, y1 = _tile_bounds(tx, ty, tile_size, w, h)
        x0, y0 = max(1, x0), max(1, y0)
        x1, y1 = min(w - 1, x1), min(h - 1, y1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                off = (y * w + x) * 3
                offsets = (
                    off,
                    off - 3,
                    off + 3,
                    off - w * 3,
                    off + w * 3,
                )
                lum = [luma(q) for q in offsets]
                if max(lum) - min(lum) < 34.0:
                    continue
                for k in range(3):
                    center = src[off + k]
                    neighbor = (
                        src[offsets[1] + k]
                        + src[offsets[2] + k]
                        + src[offsets[3] + k]
                        + src[offsets[4] + k]
                    ) * 0.25
                    img.data[off + k] = dense._clamp8(
                        center * 0.62 + neighbor * 0.38
                    )
                touched += 1
    return touched


def _filmic_subject_pixels(
    img: RGBImage,
    tiles: set[tuple[int, int]],
    tile_size: int,
) -> int:
    w, h = img.width, img.height
    cx, cy = (w - 1) * 0.5, (h - 1) * 0.48
    invx = 1.0 / max(1.0, w * 0.72)
    invy = 1.0 / max(1.0, h * 0.78)
    touched = 0
    for tx, ty in sorted(tiles):
        x0, y0, x1, y1 = _tile_bounds(tx, ty, tile_size, w, h)
        for y in range(y0, y1):
            dy = (y - cy) * invy
            for x in range(x0, x1):
                idx = y * w + x
                if math.isinf(img.depth[idx]):
                    continue
                dx = (x - cx) * invx
                r2 = dx * dx + dy * dy
                vignette = max(0.84, 1.0 - 0.12 * r2)
                off = idx * 3
                grain = (dense._noise01(x, y, 991) - 0.5) * 2.2
                vals = []
                for k in range(3):
                    v = img.data[off + k] / 255.0
                    v = max(0.0, min(1.0, (v * 1.055) / (1.0 + 0.055 * v)))
                    v = v ** 0.94
                    vals.append(dense._clamp8(v * 255.0 * vignette + grain))
                img.data[off:off + 3] = bytes(vals)
                touched += 1
    return touched


def _render_common(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float,
    pitch_deg: float,
    tile_size: int,
    scientific: bool,
) -> tuple[bytes, dict]:
    if len(positions) != len(mesh.vertices):
        raise ValueError("positions must match mesh vertices")
    if width < 64 or height < 64:
        raise ValueError("render dimensions too small")

    if scientific:
        img = RGBImage(width, height, background=(246, 248, 250))
        background_cached = False
    else:
        img = RGBImage(width, height)
        img.data[:] = _finished_background(width, height)
        background_cached = True

    view = [dense._rotate_view(p, yaw_deg, pitch_deg) for p in positions]
    projected = [
        dense._project(
            p,
            width=width,
            height=height,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
        )
        for p in positions
    ]
    normals = dense._accumulate_vertex_normals(mesh, view)
    tiles = _active_tiles(
        mesh,
        projected,
        width=width,
        height=height,
        tile_size=tile_size,
    )

    if not scientific:
        dense._subject_shadows(
            img,
            generated_objects,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
        )
    dense._render_subject_faces(img, mesh, view, projected, normals)

    fxaa_pixels = _fxaa_tiles(img, tiles, tile_size)
    filmic_pixels = 0 if scientific else _filmic_subject_pixels(
        img, tiles, tile_size
    )

    total_tiles = (
        ((width + tile_size - 1) // tile_size)
        * ((height + tile_size - 1) // tile_size)
    )
    active_pixels_upper_bound = len(tiles) * tile_size * tile_size
    return img.png_bytes(), {
        "sparse_renderer": True,
        "tile_size": tile_size,
        "active_tiles": len(tiles),
        "total_tiles": total_tiles,
        "active_tile_ratio": (
            round(len(tiles) / total_tiles, 6) if total_tiles else 0.0
        ),
        "active_pixel_upper_bound": min(
            width * height, active_pixels_upper_bound
        ),
        "frame_pixels": width * height,
        "fxaa_pixels_touched": fxaa_pixels,
        "filmic_subject_pixels": filmic_pixels,
        "background_cached": background_cached,
        "background_cache": background_cache_info(),
        "full_screen_fxaa": False,
        "full_screen_filmic": False,
        "learned_refiner": False,
        "scientific_fast_path": scientific,
    }


def render_sparse_photo_look_png(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float = 0.0,
    pitch_deg: float = -4.0,
) -> tuple[bytes, dict]:
    data, sparse = _render_common(
        mesh,
        positions,
        generated_objects=generated_objects,
        width=width,
        height=height,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        tile_size=32,
        scientific=False,
    )
    sparse.update({
        "smooth_vertex_normals": True,
        "material_profiles": True,
        "micro_surface_variation": True,
        "contact_shadows": True,
        "studio_background": True,
        "fxaa": True,
        "filmic_finish": True,
    })
    _remember_stats(sparse)
    return data, sparse


def render_scientific_fast_png(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float = 0.0,
    pitch_deg: float = 0.0,
) -> tuple[bytes, dict]:
    data, sparse = _render_common(
        mesh,
        positions,
        generated_objects=generated_objects,
        width=width,
        height=height,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        tile_size=32,
        scientific=True,
    )
    sparse.update({
        "smooth_vertex_normals": True,
        "material_profiles": True,
        "micro_surface_variation": False,
        "contact_shadows": False,
        "studio_background": False,
        "fxaa": True,
        "filmic_finish": False,
    })
    _remember_stats(sparse)
    return data, sparse


def activate_sparse_renderers(targets=("scene_graph2", "morphology", "scientific_dna")) -> dict:
    """Patch only requested current-organ engine boundaries.

    Keeping targets explicit preserves lazy organ loading: loading the scene
    organ does not import morphology or scientific-DNA modules.
    """
    wanted = set(targets)
    patched = []

    if "scene_graph2" in wanted:
        try:
            import fap_scene_graph2.engine as module
            module.render_photo_look_png = render_sparse_photo_look_png
            patched.append("scene_graph2")
        except ImportError:
            pass

    if "morphology" in wanted:
        try:
            import fap_morphology.engine as module
            module.render_photo_look_png = render_sparse_photo_look_png
            patched.append("morphology")
        except ImportError:
            pass

    if "scientific_dna" in wanted:
        try:
            import fap_scientific_geometry.engine as module
            module.render_photo_look_png = render_scientific_fast_png
            patched.append("scientific_dna")
        except ImportError:
            pass

    return {"patched": patched}
