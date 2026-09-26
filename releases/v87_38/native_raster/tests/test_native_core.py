from __future__ import annotations

from pathlib import Path

from fap_native_raster import (
    native_available,
    native_status,
    render_native_photo_look_png,
    render_native_scientific_png,
)


def test_native_library_is_loaded_in_native_ci():
    assert native_available() is True
    status = native_status()
    assert status["available"] is True
    assert status["version"] == "v87.38-c99-1"


def test_cat_raster_runs_in_c_not_python_fallback():
    from fap_object_registry.registry import build_cat_mesh

    mesh = build_cat_mesh()
    positions = [v.bind_position for v in mesh.vertices]
    data, stats = render_native_photo_look_png(
        mesh,
        positions,
        generated_objects=("cat",),
        width=256,
        height=256,
    )

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stats["native_core"] is True
    assert stats["native_fallback"] is False
    assert stats["native_backend"] == "ctypes-c99"
    assert stats["native_version"] == "v87.38-c99-1"
    assert stats["raster_pixels_touched"] > 0
    assert 0 < stats["active_tiles"] < stats["total_tiles"]
    assert stats["fxaa_pixels_touched"] >= 0
    assert stats["filmic_subject_pixels"] > 0


def test_dna_uses_native_scientific_fast_path():
    from fap_scientific_geometry.dna import build_dna_mesh, parse_dna_request

    spec = parse_dna_request("16塩基対のB-DNA")
    mesh, positions, _ = build_dna_mesh(spec)
    data, stats = render_native_scientific_png(
        mesh,
        positions,
        generated_objects=("dna",),
        width=256,
        height=320,
        yaw_deg=28.0,
        pitch_deg=-10.0,
    )

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stats["native_core"] is True
    assert stats["scientific_fast_path"] is True
    assert stats["studio_background"] is False
    assert stats["filmic_finish"] is False
    assert stats["filmic_subject_pixels"] == 0
    assert stats["raster_pixels_touched"] > 0


def test_native_patch_targets_only_requested_organ():
    from fap_native_raster import activate_native_renderers

    result = activate_native_renderers(("scientific_dna",))
    assert result["native"]["available"] is True
    assert "scientific_dna" in result["patched"]
    assert "scene_graph2" not in result["patched"]
    assert "morphology" not in result["patched"]
