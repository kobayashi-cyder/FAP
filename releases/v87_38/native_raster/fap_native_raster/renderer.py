from __future__ import annotations

import ctypes
import math
from typing import Sequence

from fap_human_lbs.core import Mesh, RGBImage
from fap_photo_look import renderer as dense
from fap_sparse_execution import renderer as sparse

from .loader import (
    flatten_doubles,
    flatten_i32,
    flatten_u8,
    load_native_core,
    native_status,
)


Vec3 = tuple[float, float, float]


def _native_render(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float,
    pitch_deg: float,
    scientific: bool,
) -> tuple[bytes, dict]:
    lib = load_native_core(False)
    if lib is None:
        fallback = (
            sparse.render_scientific_fast_png
            if scientific
            else sparse.render_sparse_photo_look_png
        )
        data, stats = fallback(
            mesh,
            positions,
            generated_objects=generated_objects,
            width=width,
            height=height,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
        )
        stats = dict(stats)
        stats.update({
            "native_core": False,
            "native_fallback": True,
            "native_status": native_status(),
        })
        sparse._remember_stats(stats)
        return data, stats

    if len(positions) != len(mesh.vertices):
        raise ValueError("positions must match mesh vertices")

    if scientific:
        img = RGBImage(width, height, background=(246, 248, 250))
        background_cached = False
    else:
        img = RGBImage(width, height)
        img.data[:] = sparse._finished_background(width, height)
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
    tiles = sparse._active_tiles(
        mesh,
        projected,
        width=width,
        height=height,
        tile_size=32,
    )

    if not scientific:
        dense._subject_shadows(
            img,
            generated_objects,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
        )

    rgb = (ctypes.c_uint8 * len(img.data)).from_buffer(img.data)
    depth = (ctypes.c_float * (width * height))()
    projected_c = flatten_doubles(projected)
    normals_c = flatten_doubles(normals)
    faces_c = flatten_i32((f.a, f.b, f.c) for f in mesh.faces)
    colors_c = flatten_u8(f.color for f in mesh.faces)
    tile_rows = sorted(tiles)
    tiles_c = flatten_i32(tile_rows) if tile_rows else (ctypes.c_int32 * 0)()

    raster_pixels = int(lib.fap_raster_subject(
        rgb,
        depth,
        width,
        height,
        projected_c,
        normals_c,
        faces_c,
        colors_c,
        len(mesh.faces),
    ))

    fxaa_pixels = 0
    if tile_rows:
        fxaa_pixels = int(lib.fap_fxaa_tiles(
            rgb,
            width,
            height,
            tiles_c,
            len(tile_rows),
            32,
        ))

    filmic_pixels = 0
    if not scientific and tile_rows:
        filmic_pixels = int(lib.fap_filmic_subject(
            rgb,
            depth,
            width,
            height,
            tiles_c,
            len(tile_rows),
            32,
        ))

    total_tiles = ((width + 31) // 32) * ((height + 31) // 32)
    status = native_status()
    stats = {
        "sparse_renderer": True,
        "native_core": True,
        "native_fallback": False,
        "native_backend": "ctypes-c99",
        "native_version": status.get("version"),
        "tile_size": 32,
        "active_tiles": len(tiles),
        "total_tiles": total_tiles,
        "active_tile_ratio": round(len(tiles) / total_tiles, 6) if total_tiles else 0.0,
        "raster_pixels_touched": raster_pixels,
        "fxaa_pixels_touched": fxaa_pixels,
        "filmic_subject_pixels": filmic_pixels,
        "background_cached": background_cached,
        "background_cache": sparse.background_cache_info(),
        "full_screen_fxaa": False,
        "full_screen_filmic": False,
        "scientific_fast_path": scientific,
        "smooth_vertex_normals": True,
        "material_profiles": True,
        "micro_surface_variation": not scientific,
        "contact_shadows": not scientific,
        "studio_background": not scientific,
        "fxaa": True,
        "filmic_finish": not scientific,
        "learned_refiner": False,
    }
    sparse._remember_stats(stats)
    return img.png_bytes(), stats


def render_native_photo_look_png(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float = 0.0,
    pitch_deg: float = -4.0,
) -> tuple[bytes, dict]:
    return _native_render(
        mesh,
        positions,
        generated_objects=generated_objects,
        width=width,
        height=height,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        scientific=False,
    )


def render_native_scientific_png(
    mesh: Mesh,
    positions: Sequence[Vec3],
    *,
    generated_objects: Sequence[str],
    width: int,
    height: int,
    yaw_deg: float = 0.0,
    pitch_deg: float = 0.0,
) -> tuple[bytes, dict]:
    return _native_render(
        mesh,
        positions,
        generated_objects=generated_objects,
        width=width,
        height=height,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        scientific=True,
    )


def activate_native_renderers(targets=("scene_graph2", "morphology", "scientific_dna")) -> dict:
    wanted = set(targets)
    patched = []
    if "scene_graph2" in wanted:
        try:
            import fap_scene_graph2.engine as module
            module.render_photo_look_png = render_native_photo_look_png
            patched.append("scene_graph2")
        except ImportError:
            pass
    if "morphology" in wanted:
        try:
            import fap_morphology.engine as module
            module.render_photo_look_png = render_native_photo_look_png
            patched.append("morphology")
        except ImportError:
            pass
    if "scientific_dna" in wanted:
        try:
            import fap_scientific_geometry.engine as module
            module.render_photo_look_png = render_native_scientific_png
            patched.append("scientific_dna")
        except ImportError:
            pass
    return {
        "patched": patched,
        "native": native_status(),
    }
