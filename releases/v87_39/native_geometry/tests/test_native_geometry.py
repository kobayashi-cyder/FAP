from __future__ import annotations

import math

from fap_human_lbs.core import (
    Pose,
    build_human_mesh,
    default_human_skeleton,
    skinned_positions,
)
from fap_native_geometry import (
    NativeLBSCache,
    native_cat_pattern,
    native_geometry_status,
    prepare_geometry,
)
from fap_object_registry.registry import build_cat_mesh
from fap_photo_look import renderer as dense
from fap_sparse_execution import renderer as sparse
from fap_morphology.pattern import apply_cat_pattern as python_cat_pattern


def _close3(a,b,tol=1e-8):
    return all(abs(x-y)<=tol for x,y in zip(a,b))


def test_native_geometry_library_loaded():
    s=native_geometry_status()
    assert s["available"] is True
    assert s["version"]=="v87.39-c99-1"


def test_native_projection_normals_and_tiles_match_python():
    mesh=build_cat_mesh()
    positions=[v.bind_position for v in mesh.vertices]
    width=256; height=256; yaw=11.0; pitch=-4.0
    native=prepare_geometry(
        mesh,positions,width=width,height=height,
        yaw_deg=yaw,pitch_deg=pitch,tile_size=32,
    )

    view=[dense._rotate_view(p,yaw,pitch) for p in positions]
    projected=[dense._project(p,width=width,height=height,yaw_deg=yaw,pitch_deg=pitch) for p in positions]
    normals=dense._accumulate_vertex_normals(mesh,view)
    tiles=sparse._active_tiles(mesh,projected,width=width,height=height,tile_size=32)

    for i,p in enumerate(projected):
        got=(native.projected[i*3],native.projected[i*3+1],native.projected[i*3+2])
        assert _close3(got,p,1e-8)
    for i,n in enumerate(normals):
        got=(native.normals[i*3],native.normals[i*3+1],native.normals[i*3+2])
        assert _close3(got,n,1e-8)
    assert set(native.tile_rows)==set(tiles)


def test_native_cat_pattern_matches_python_reference():
    mesh=build_cat_mesh()
    attrs={"coat_pattern":"calico","face_pattern":"hachiware"}
    py,meta_py=python_cat_pattern(mesh,attrs)
    native,meta_native=native_cat_pattern(mesh,attrs)
    assert meta_native==meta_py
    assert [f.color for f in native.faces]==[f.color for f in py.faces]


def test_native_lbs_matches_full_python():
    sk=default_human_skeleton()
    mesh=build_human_mesh(sk)
    pose=Pose({
        "r_shoulder":(0.0,0.0,-82.0),
        "r_elbow":(0.0,0.0,-72.0),
        "neck":(0.0,25.0,0.0),
    })
    expected=skinned_positions(mesh,sk,pose)
    cache=NativeLBSCache()
    got,stats=cache.skin(mesh,sk,pose)
    assert stats["native_lbs"] is True
    assert stats["updated_vertices"]==len(mesh.vertices)
    for a,b in zip(got,expected):
        assert _close3(a,b,1e-8)


def test_sparse_lbs_updates_only_affected_vertices_and_stays_exact():
    sk=default_human_skeleton()
    mesh=build_human_mesh(sk)
    cache=NativeLBSCache()
    base=Pose({})
    cache.skin(mesh,sk,base)

    pose=Pose({"neck":(0.0,25.0,0.0),"head":(0.0,15.0,0.0)})
    got,stats=cache.skin(mesh,sk,pose)
    expected=skinned_positions(mesh,sk,pose)

    assert 0 < stats["updated_vertices"] < len(mesh.vertices)
    assert 0 < stats["affected_bones"] < stats["bone_count"]
    for a,b in zip(got,expected):
        assert _close3(a,b,1e-8)
