from __future__ import annotations

import importlib


def test_gateway_status_does_not_load_media_organs():
    g = importlib.import_module("fap_v87_37_sparse_unified_chat_gateway")
    core = g.FAPV8737Unified()

    status = core.status()
    sparse = status["sparse_execution"]

    assert sparse["organs_loaded"] == []
    assert sparse["organ_load_count"] == 0
    assert sparse["top_k"] == 1


def test_capability_query_keeps_organs_cold():
    g = importlib.import_module("fap_v87_37_sparse_unified_chat_gateway")
    core = g.FAPV8737Unified()

    reply = core._latest_image_capability()

    assert reply["ok"] is True
    assert core.organ_pool.loaded() == ()
    assert core.organ_pool.load_count == 0
