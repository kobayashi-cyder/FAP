from __future__ import annotations

from pathlib import Path

from fap_sparse_execution.routing import LazyOrganPool, SparseOrganRouter


def test_sparse_router_activates_exactly_one_organ():
    router = SparseOrganRouter()

    scene = router.route("鳥と犬を描いて")
    cat = router.route("三毛の八割れ猫を描いて")
    dna = router.route("20塩基対のB-DNAを描いて")

    assert scene.active_count == 1
    assert cat.active_count == 1
    assert dna.active_count == 1
    assert scene.organ_id == "scene"
    assert cat.organ_id == "cat_morphology"
    assert dna.organ_id == "scientific_dna"


def test_lazy_pool_does_not_construct_unused_organs():
    pool = LazyOrganPool()
    calls = []

    pool.register("a", lambda: calls.append("a") or {"id": "a"})
    pool.register("b", lambda: calls.append("b") or {"id": "b"})

    assert pool.loaded() == ()
    assert pool.load_count == 0

    first = pool.get("a")
    again = pool.get("a")

    assert first is again
    assert calls == ["a"]
    assert pool.loaded() == ("a",)
    assert pool.load_count == 1
    assert not pool.is_loaded("b")


def test_sparse_photo_renderer_uses_subset_of_tiles():
    from fap_object_registry.registry import build_cat_mesh
    from fap_sparse_execution.renderer import render_sparse_photo_look_png

    mesh = build_cat_mesh()
    positions = [v.bind_position for v in mesh.vertices]
    data, stats = render_sparse_photo_look_png(
        mesh,
        positions,
        generated_objects=("cat",),
        width=256,
        height=256,
    )

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stats["sparse_renderer"] is True
    assert 0 < stats["active_tiles"] < stats["total_tiles"]
    assert stats["active_tile_ratio"] < 1.0
    assert stats["full_screen_fxaa"] is False
    assert stats["full_screen_filmic"] is False
    assert stats["background_cached"] is True


def test_finished_background_is_reused():
    from fap_object_registry.registry import build_cat_mesh
    from fap_sparse_execution.renderer import (
        background_cache_info,
        render_sparse_photo_look_png,
    )

    mesh = build_cat_mesh()
    positions = [v.bind_position for v in mesh.vertices]

    before = background_cache_info()
    render_sparse_photo_look_png(
        mesh,
        positions,
        generated_objects=("cat",),
        width=258,
        height=258,
    )
    middle = background_cache_info()
    render_sparse_photo_look_png(
        mesh,
        positions,
        generated_objects=("cat",),
        width=258,
        height=258,
    )
    after = background_cache_info()

    assert middle["misses"] >= before["misses"] + 1
    assert after["hits"] >= middle["hits"] + 1


def test_dna_scientific_renderer_skips_photo_filmic():
    from fap_scientific_geometry.dna import build_dna_mesh, parse_dna_request
    from fap_sparse_execution.renderer import render_scientific_fast_png

    spec = parse_dna_request("12塩基対のB-DNA")
    mesh, positions, _ = build_dna_mesh(spec)
    data, stats = render_scientific_fast_png(
        mesh,
        positions,
        generated_objects=("dna",),
        width=256,
        height=320,
        yaw_deg=28.0,
        pitch_deg=-10.0,
    )

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert stats["scientific_fast_path"] is True
    assert stats["filmic_finish"] is False
    assert stats["background_cached"] is False
    assert stats["full_screen_fxaa"] is False
    assert stats["active_tiles"] < stats["total_tiles"]


def test_sparse_renderer_patch_is_target_scoped():
    from fap_sparse_execution.renderer import activate_sparse_renderers

    result = activate_sparse_renderers(("scientific_dna",))
    assert "scientific_dna" in result["patched"]
    assert "scene_graph2" not in result["patched"]
    assert "morphology" not in result["patched"]
