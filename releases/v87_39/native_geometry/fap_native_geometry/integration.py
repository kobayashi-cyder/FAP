from __future__ import annotations

import threading

from fap_human_lbs.core import (
    build_human_mesh, default_human_skeleton, pose_from_prompt, v_add
)

from .geometry import NativeLBSCache, native_cat_pattern
from .renderer import (
    render_native_geometry_photo_png,
    render_native_geometry_scientific_png,
)
from .loader import native_geometry_status

_PY_CAT_PATTERN=None
_PY_SKINNED=None
_HUMAN_SK=None
_HUMAN_MESH=None
_LBS=NativeLBSCache()
_LBS_LOCK=threading.Lock()
_LAST_LBS={}

def last_lbs_stats():
    return dict(_LAST_LBS)

def native_skinned_positions(mesh,skeleton,pose):
    global _LAST_LBS
    with _LBS_LOCK:
        positions,stats=_LBS.skin(mesh,skeleton,pose)
    _LAST_LBS=dict(stats)
    return positions

def _human_mesh_and_positions(node,center,text):
    global _HUMAN_SK,_HUMAN_MESH,_LAST_LBS
    if _HUMAN_SK is None:
        _HUMAN_SK=default_human_skeleton()
        _HUMAN_MESH=build_human_mesh(_HUMAN_SK)
    pose_text=text
    if node.state=="sitting": pose_text+=" 座る"
    elif node.state=="walking": pose_text+=" 歩く"
    elif node.state=="standing": pose_text+=" 直立 腕を下げる"
    pose=pose_from_prompt(pose_text)
    with _LBS_LOCK:
        positions,stats=_LBS.skin(_HUMAN_MESH,_HUMAN_SK,pose)
    _LAST_LBS=dict(stats)
    pts=[v_add(p,center) for p in positions]
    return _HUMAN_MESH,pts,{
        "geometry":"human-lbs-native-sparse",
        "pose_bones":sorted(pose.rotations),
        "state_applied":node.state in {"default","sitting","walking","standing"},
        **stats,
    }

def activate_native_geometry(targets=("scene_graph2","morphology","scientific_dna","human_lbs")):
    global _PY_CAT_PATTERN,_PY_SKINNED
    wanted=set(targets)
    patched=[]

    if "scene_graph2" in wanted:
        try:
            import fap_scene_graph2.engine as m
            m.render_photo_look_png=render_native_geometry_photo_png
            m._human_mesh_and_positions=_human_mesh_and_positions
            m.skinned_positions=native_skinned_positions
            patched.append("scene_graph2")
        except ImportError:
            pass

    if "morphology" in wanted:
        try:
            import fap_morphology.engine as m
            m.render_photo_look_png=render_native_geometry_photo_png
            if _PY_CAT_PATTERN is None:
                _PY_CAT_PATTERN=m.apply_cat_pattern
            def wrapped(mesh,attrs):
                return native_cat_pattern(mesh,attrs,fallback=_PY_CAT_PATTERN)
            m.apply_cat_pattern=wrapped
            patched.append("morphology")
        except ImportError:
            pass

    if "scientific_dna" in wanted:
        try:
            import fap_scientific_geometry.engine as m
            m.render_photo_look_png=render_native_geometry_scientific_png
            patched.append("scientific_dna")
        except ImportError:
            pass

    if "human_lbs" in wanted:
        try:
            import fap_human_lbs.core as core
            if _PY_SKINNED is None:
                _PY_SKINNED=core.skinned_positions
            core.skinned_positions=native_skinned_positions
            patched.append("human_lbs")
        except ImportError:
            pass

    return {"patched":patched,"native_geometry":native_geometry_status()}
