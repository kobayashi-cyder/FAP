from __future__ import annotations

from fap_native_geometry import (
    render_native_geometry_photo_png,
    render_native_geometry_scientific_png,
)
from fap_object_registry.registry import build_cat_mesh
from fap_scientific_geometry.dna import build_dna_mesh, parse_dna_request


def test_v8739_photo_path_is_geometry_and_raster_native():
    mesh=build_cat_mesh()
    pos=[v.bind_position for v in mesh.vertices]
    data,stats=render_native_geometry_photo_png(
        mesh,pos,generated_objects=("cat",),width=256,height=256
    )
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stats["native_core"] is True
    assert stats["native_geometry"] is True
    assert stats["projection_native"] is True
    assert stats["normal_accumulation_native"] is True
    assert stats["active_tile_discovery_native"] is True


def test_v8739_dna_path_remains_scientific_fast():
    spec=parse_dna_request("12塩基対のB-DNA")
    mesh,pos,_=build_dna_mesh(spec)
    data,stats=render_native_geometry_scientific_png(
        mesh,pos,generated_objects=("dna",),width=256,height=320,
        yaw_deg=28.0,pitch_deg=-10.0,
    )
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stats["native_geometry"] is True
    assert stats["scientific_fast_path"] is True
    assert stats["filmic_finish"] is False
