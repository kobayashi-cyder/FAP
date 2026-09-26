from __future__ import annotations

import importlib
import json
from pathlib import Path

_runtime = None
_storage_dir: Path | None = None
_main_sha = "unknown"
_release_version = "1.0.01"
_verified_count = 0


def _read_meta() -> None:
    global _main_sha, _release_version
    try:
        meta = importlib.import_module("build_meta")
        _main_sha = str(getattr(meta, "MAIN_SHA", "unknown"))
        _release_version = str(getattr(meta, "RELEASE_VERSION", "1.0.01"))
    except Exception:
        pass


def initialize(storage_dir: str) -> str:
    global _runtime, _storage_dir, _verified_count
    _storage_dir = Path(storage_dir)
    _storage_dir.mkdir(parents=True, exist_ok=True)
    _read_meta()

    from fap_1x_standard_runtime import FAP1xStandardRuntime

    _runtime = FAP1xStandardRuntime(
        root=Path(__file__).resolve().parent,
        memory_root=_storage_dir / "semantic_memory",
        max_history_messages=48,
    )

    log_path = _storage_dir / "verification.jsonl"
    if log_path.exists():
        try:
            _verified_count = sum(1 for _ in log_path.open("r", encoding="utf-8"))
        except Exception:
            _verified_count = 0

    return json.dumps(_status_payload(), ensure_ascii=False)


def run(query: str) -> str:
    if _runtime is None:
        raise RuntimeError("FAP 1.x runtime is not initialized")

    result = _runtime.run_turn(str(query), session_id="android")
    payload = dict(result.payload or {})
    answer = ""
    for key in ("text", "reply", "message"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            answer = str(value)
            break

    confidence = payload.get("confidence", 0.5)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except Exception:
        confidence = 0.5

    return json.dumps(
        {
            "answer": answer,
            "skill": str(result.endpoint_id or "unhandled"),
            "confidence": confidence,
            "state": str(result.state),
            "status": _status_payload()["status"],
        },
        ensure_ascii=False,
    )


def verify(query: str, answer: str, success: bool) -> str:
    global _verified_count
    if _storage_dir is None:
        raise RuntimeError("FAP 1.x runtime is not initialized")

    record = {
        "query": str(query),
        "answer": str(answer),
        "success": bool(success),
        "runtime": "FAP1xStandardRuntime",
        "release": _release_version,
        "main_sha": _main_sha,
    }
    with (_storage_dir / "verification.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    _verified_count += 1
    return json.dumps(_status_payload(), ensure_ascii=False)


def clear() -> str:
    global _verified_count
    if _storage_dir is not None:
        for name in ("verification.jsonl",):
            try:
                (_storage_dir / name).unlink(missing_ok=True)
            except Exception:
                pass
        memory = _storage_dir / "semantic_memory"
        if memory.exists():
            for path in sorted(memory.rglob("*"), reverse=True):
                try:
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                except Exception:
                    pass

    _verified_count = 0
    if _runtime is not None:
        try:
            _runtime._histories.clear()
        except Exception:
            pass
    return json.dumps(_status_payload(), ensure_ascii=False)


def _status_payload() -> dict:
    endpoint_count = 0
    memory_on = False
    try:
        endpoint_count = len(_runtime.fabric.endpoint_ids) if _runtime is not None else 0
        memory_on = bool(_runtime is not None and _runtime.memory is not None)
    except Exception:
        pass

    return {
        "status": (
            f"READY · FAP 1.0.01 Pixel · endpoints={endpoint_count} · "
            f"memory={'ON' if memory_on else 'OFF'} · verified={_verified_count}"
        ),
        "runtime": "FAP1xStandardRuntime",
        "release": _release_version,
        "main_sha": _main_sha,
        "verified": _verified_count,
        "pixel_browser": True,
    }


def status() -> str:
    return json.dumps(_status_payload(), ensure_ascii=False)
