#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time

from fap_human_lbs.core import Pose,build_human_mesh,default_human_skeleton,skinned_positions
from fap_native_geometry import NativeLBSCache,render_native_geometry_photo_png
from fap_native_raster import render_native_photo_look_png
from fap_object_registry.registry import build_cat_mesh


def median(fn,n=5):
    samples=[]
    for _ in range(n):
        t=time.perf_counter(); fn(); samples.append(time.perf_counter()-t)
    return statistics.median(samples)


def main():
    cat=build_cat_mesh()
    pos=[v.bind_position for v in cat.vertices]
    render_native_photo_look_png(cat,pos,generated_objects=("cat",),width=384,height=384)
    render_native_geometry_photo_png(cat,pos,generated_objects=("cat",),width=384,height=384)
    v38=median(lambda:render_native_photo_look_png(cat,pos,generated_objects=("cat",),width=384,height=384),3)
    v39=median(lambda:render_native_geometry_photo_png(cat,pos,generated_objects=("cat",),width=384,height=384),3)

    sk=default_human_skeleton()
    mesh=build_human_mesh(sk)
    base=Pose({})
    look=Pose({"neck":(0.0,25.0,0.0),"head":(0.0,15.0,0.0)})
    cache=NativeLBSCache()
    cache.skin(mesh,sk,base)
    py_lbs=median(lambda:skinned_positions(mesh,sk,look),20)
    native_sparse=median(lambda:cache.skin(mesh,sk,look),20)

    print(json.dumps({
        "v38_render_seconds":round(v38,6),
        "v39_render_seconds":round(v39,6),
        "render_speedup_x":round(v38/v39,3) if v39 else 0.0,
        "python_lbs_seconds":round(py_lbs,6),
        "native_sparse_lbs_seconds":round(native_sparse,6),
        "lbs_speedup_x":round(py_lbs/native_sparse,3) if native_sparse else 0.0,
    }))


if __name__=="__main__":
    main()
