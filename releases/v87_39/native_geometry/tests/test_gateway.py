from __future__ import annotations

import importlib


def test_v8739_gateway_starts_with_media_organs_cold():
    g=importlib.import_module("fap_v87_39_native_geometry_gateway")
    core=g.FAPV8739Unified()
    assert core.organ_pool.loaded()==()
    assert core.organ_pool.load_count==0


def test_v8739_status_reports_geometry_backend():
    g=importlib.import_module("fap_v87_39_native_geometry_gateway")
    core=g.FAPV8739Unified()
    s=core.status()
    assert s["version"]=="87.39-unified-chat"
    assert s["native_geometry"]["available"] is True
    assert s["native_geometry"]["version"]=="v87.39-c99-1"
