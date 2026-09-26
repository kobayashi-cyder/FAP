from __future__ import annotations

import json

_core = None
_verified = 0


def initialize(storage_dir: str) -> str:
    global _core
    from fap_runtime_1x import CORE
    _core = CORE
    return json.dumps(_status_payload(), ensure_ascii=False)


def run(query: str) -> str:
    if _core is None:
        raise RuntimeError("FAP runtime is not initialized")
    result = _core.chat_result(str(query))
    payload = result.get("payload") or {}
    return json.dumps({
        "answer": str(payload.get("reply", "")),
        "skill": str(result.get("endpoint_id", "local-1x")),
        "confidence": float(payload.get("confidence", 0.0) or 0.0),
        "status": _status_payload()["status"],
    }, ensure_ascii=False)


def verify(query: str, answer: str, success: bool) -> str:
    global _verified
    if _core is None:
        raise RuntimeError("FAP runtime is not initialized")
    _core.verify(str(query), str(answer), bool(success))
    _verified += 1
    return json.dumps(_status_payload(), ensure_ascii=False)


def clear() -> str:
    global _verified
    _verified = 0
    return json.dumps(_status_payload(), ensure_ascii=False)


def _status_payload() -> dict:
    core_status = _core.chat_status() if _core is not None else {
        "version": "1.0.01-unified-chat",
        "mainline_version": "1.0.01",
    }
    return {
        "status": f"READY · FAP 1.0.01 · verified={_verified}",
        "runtime": "fap_runtime_1x",
        "release": "1.0.01",
        "verified": _verified,
        "core": core_status,
    }


def status() -> str:
    return json.dumps(_status_payload(), ensure_ascii=False)
