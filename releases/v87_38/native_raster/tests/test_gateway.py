from __future__ import annotations

import importlib


def test_v8738_gateway_keeps_media_organs_lazy():
    g = importlib.import_module("fap_v87_38_native_unified_chat_gateway")
    core = g.FAPV8738Unified()
    assert core.organ_pool.loaded() == ()
    assert core.organ_pool.load_count == 0


def test_v8738_status_reports_native_backend():
    g = importlib.import_module("fap_v87_38_native_unified_chat_gateway")
    core = g.FAPV8738Unified()
    status = core.status()
    assert status["version"] == "87.38-unified-chat"
    assert status["native_raster"]["available"] is True
    assert status["native_raster"]["version"] == "v87.38-c99-1"
