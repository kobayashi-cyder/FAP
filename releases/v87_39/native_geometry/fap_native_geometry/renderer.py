from __future__ import annotations

import ctypes
from typing import Sequence

from fap_human_lbs.core import Mesh, RGBImage
from fap_photo_look import renderer as dense
from fap_sparse_execution import renderer as sparse
from fap_native_raster.loader import load_native_core, native_status as raster_status

from .geometry import prepare_geometry
from .loader import load_native_geometry, native_geometry_status

Vec3=tuple[float,float,float]

def _render(mesh:Mesh, positions:Sequence[Vec3], *, generated_objects:Sequence[str],
            width:int,height:int,yaw_deg:float,pitch_deg:float,scientific:bool):
    glib=load_native_geometry(False)
    rlib=load_native_core(False)
    if glib is None or rlib is None:
        from fap_native_raster.renderer import (
            render_native_photo_look_png, render_native_scientific_png
        )
        fn=render_native_scientific_png if scientific else render_native_photo_look_png
        data,stats=fn(mesh,positions,generated_objects=generated_objects,width=width,height=height,
                      yaw_deg=yaw_deg,pitch_deg=pitch_deg)
        stats=dict(stats)
        stats.update({
            "native_geometry":False,
            "native_geometry_fallback":True,
            "native_geometry_status":native_geometry_status(),
        })
        sparse._remember_stats(stats)
        return data,stats

    if scientific:
        img=RGBImage(width,height,background=(246,248,250))
        background_cached=False
    else:
        img=RGBImage(width,height)
        img.data[:]=sparse._finished_background(width,height)
        background_cached=True

    prep=prepare_geometry(
        mesh,positions,width=width,height=height,
        yaw_deg=yaw_deg,pitch_deg=pitch_deg,tile_size=32,
    )
    if not scientific:
        dense._subject_shadows(
            img,generated_objects,yaw_deg=yaw_deg,pitch_deg=pitch_deg
        )

    rgb=(ctypes.c_uint8*len(img.data)).from_buffer(img.data)
    depth=(ctypes.c_float*(width*height))()
    raster_pixels=int(rlib.fap_raster_subject(
        rgb,depth,width,height,prep.projected,prep.normals,
        prep.faces,prep.colors,prep.face_count,
    ))
    tile_count=len(prep.tile_rows)
    fxaa_pixels=0
    if tile_count:
        fxaa_pixels=int(rlib.fap_fxaa_tiles(
            rgb,width,height,prep.tiles,tile_count,32
        ))
    filmic_pixels=0
    if not scientific and tile_count:
        filmic_pixels=int(rlib.fap_filmic_subject(
            rgb,depth,width,height,prep.tiles,tile_count,32
        ))

    total_tiles=((width+31)//32)*((height+31)//32)
    stats={
        "sparse_renderer":True,
        "native_core":True,
        "native_geometry":True,
        "native_geometry_fallback":False,
        "native_backend":"ctypes-c99-geometry+raster",
        "native_raster_version":raster_status().get("version"),
        "native_geometry_version":native_geometry_status().get("version"),
        "projection_native":True,
        "normal_accumulation_native":True,
        "active_tile_discovery_native":True,
        "tile_size":32,
        "active_tiles":tile_count,
        "total_tiles":total_tiles,
        "active_tile_ratio":round(tile_count/total_tiles,6) if total_tiles else 0.0,
        "raster_pixels_touched":raster_pixels,
        "fxaa_pixels_touched":fxaa_pixels,
        "filmic_subject_pixels":filmic_pixels,
        "background_cached":background_cached,
        "background_cache":sparse.background_cache_info(),
        "scientific_fast_path":scientific,
        "studio_background":not scientific,
        "contact_shadows":not scientific,
        "filmic_finish":not scientific,
        "full_screen_fxaa":False,
        "full_screen_filmic":False,
        "learned_refiner":False,
    }
    sparse._remember_stats(stats)
    return img.png_bytes(),stats

def render_native_geometry_photo_png(
    mesh:Mesh,positions:Sequence[Vec3],*,generated_objects:Sequence[str],
    width:int,height:int,yaw_deg:float=0.0,pitch_deg:float=-4.0
):
    return _render(mesh,positions,generated_objects=generated_objects,width=width,height=height,
                   yaw_deg=yaw_deg,pitch_deg=pitch_deg,scientific=False)

def render_native_geometry_scientific_png(
    mesh:Mesh,positions:Sequence[Vec3],*,generated_objects:Sequence[str],
    width:int,height:int,yaw_deg:float=0.0,pitch_deg:float=0.0
):
    return _render(mesh,positions,generated_objects=generated_objects,width=width,height=height,
                   yaw_deg=yaw_deg,pitch_deg=pitch_deg,scientific=True)
