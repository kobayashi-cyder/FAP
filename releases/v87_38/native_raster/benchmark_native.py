#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time

from fap_object_registry.registry import build_cat_mesh
from fap_sparse_execution.renderer import render_sparse_photo_look_png
from fap_native_raster import render_native_photo_look_png, native_status


def measure(fn, mesh, positions, repeats=3):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        data, stats = fn(
            mesh,
            positions,
            generated_objects=("cat",),
            width=384,
            height=384,
        )
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples), stats


def main():
    mesh = build_cat_mesh()
    positions = [v.bind_position for v in mesh.vertices]

    # Warm resolution-specific background cache before measuring.
    render_sparse_photo_look_png(
        mesh, positions, generated_objects=("cat",), width=384, height=384
    )
    render_native_photo_look_png(
        mesh, positions, generated_objects=("cat",), width=384, height=384
    )

    py_seconds, py_stats = measure(
        render_sparse_photo_look_png, mesh, positions
    )
    native_seconds, native_stats = measure(
        render_native_photo_look_png, mesh, positions
    )
    speedup = py_seconds / native_seconds if native_seconds > 0 else 0.0

    result = {
        "native": native_status(),
        "python_median_seconds": round(py_seconds, 6),
        "native_median_seconds": round(native_seconds, 6),
        "speedup_x": round(speedup, 3),
        "active_tiles": native_stats.get("active_tiles"),
        "total_tiles": native_stats.get("total_tiles"),
        "native_raster_pixels": native_stats.get("raster_pixels_touched"),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
