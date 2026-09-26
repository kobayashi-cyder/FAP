from __future__ import annotations

import importlib
import inspect
import json
import os
import re
from pathlib import Path
from typing import Any

_runtime = None
_runtime_name = "none"
_storage_dir: Path | None = None
_release_version = "unknown"
_core_source = "unknown"
_main_sha = "unknown"
_autonomy_loaded = False
_verified_count = 0


def _read_meta() -> None:
    global _release_version, _core_source, _main_sha
    try:
        meta = importlib.import_module("build_meta")
        _release_version = str(getattr(meta, "RELEASE_VERSION", "unknown"))
        _core_source = str(getattr(meta, "CORE_SOURCE", "unknown"))
        _main_sha = str(getattr(meta, "MAIN_SHA", "unknown"))
    except Exception:
        pass


def _patch_storage(module: Any) -> None:
    if _storage_dir is None:
        return
    os.environ["FAP_ANDROID_DATA_DIR"] = str(_storage_dir)
    if hasattr(module, "MEMORY_FILE"):
        try:
            module.MEMORY_FILE = _storage_dir / "fap_memory.json"
        except Exception:
            pass


def _select_runtime(module: Any):
    candidates = []
    for name, obj in vars(module).items():
        match = re.fullmatch(r"FAPV(\d+)", name)
        if match and inspect.isclass(obj):
            candidates.append((int(match.group(1)), name, obj))

    errors = []
    for _, name, cls in sorted(candidates, reverse=True):
        try:
            instance = cls()
            if callable(getattr(instance, "think", None)):
                return name, instance
        except Exception as exc:
            errors.append(f"{name}:{type(exc).__name__}")

    raise RuntimeError("No runnable FAPVxx class: " + ",".join(errors[:8]))


def initialize(storage_dir: str) -> str:
    global _runtime, _runtime_name, _storage_dir, _autonomy_loaded, _verified_count
    _storage_dir = Path(storage_dir)
    _storage_dir.mkdir(parents=True, exist_ok=True)
    _read_meta()

    core = importlib.import_module("fap_core")
    _patch_storage(core)
    _runtime_name, _runtime = _select_runtime(core)

    try:
        importlib.import_module("fap_autonomy")
        _autonomy_loaded = True
    except Exception:
        _autonomy_loaded = False

    log_path = _storage_dir / "verification.jsonl"
    if log_path.exists():
        try:
            _verified_count = sum(1 for _ in log_path.open("r", encoding="utf-8"))
        except Exception:
            _verified_count = 0

    return json.dumps(_status_payload(), ensure_ascii=False)


def _jsonable(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return str(value)


def _confidence(state: Any) -> float:
    if isinstance(state, dict):
        for key in ("confidence", "final_confidence", "score"):
            try:
                if key in state:
                    return max(0.0, min(1.0, float(state[key])))
            except Exception:
                pass
        organs = state.get("organs")
        if isinstance(organs, dict):
            integ = organs.get("integrate")
            if isinstance(integ, dict):
                try:
                    return max(0.0, min(1.0, float(integ.get("confidence", 0.5))))
                except Exception:
                    pass
    return 0.5


def _answer(state: Any) -> str:
    if _runtime is not None and callable(getattr(_runtime, "verbalize", None)):
        try:
            text = _runtime.verbalize(state)
            if text is not None:
                return str(text)
        except Exception:
            pass
    if isinstance(state, dict):
        for key in ("answer", "text", "response", "output"):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return json.dumps(_jsonable(state), ensure_ascii=False, indent=2)


def run(query: str) -> str:
    if _runtime is None:
        raise RuntimeError("FAP runtime is not initialized")
    state = _runtime.think(str(query))
    payload = {
        "answer": _answer(state),
        "skill": f"python:{_runtime_name}",
        "confidence": _confidence(state),
        "state_version": str(state.get("version", "")) if isinstance(state, dict) else "",
        "status": _status_payload()["status"],
    }
    return json.dumps(payload, ensure_ascii=False)


def _learn_verified(answer: str) -> None:
    if _runtime is None or not callable(getattr(_runtime, "learn", None)):
        return
    text = str(answer).strip()
    if not text:
        return
    attempts = (
        lambda: _runtime.learn(text, 0.85, "verified_android"),
        lambda: _runtime.learn(text, weight=0.85, source="verified_android"),
        lambda: _runtime.learn(text),
    )
    for attempt in attempts:
        try:
            attempt()
            return
        except TypeError:
            continue
        except Exception:
            return


def verify(query: str, answer: str, success: bool) -> str:
    global _verified_count
    if _storage_dir is None:
        raise RuntimeError("FAP runtime is not initialized")
    record = {
        "query": str(query),
        "answer": str(answer),
        "success": bool(success),
        "runtime": _runtime_name,
        "release": _release_version,
        "main_sha": _main_sha,
    }
    with (_storage_dir / "verification.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    _verified_count += 1
    if success:
        _learn_verified(answer)
    return json.dumps(_status_payload(), ensure_ascii=False)


def clear() -> str:
    global _verified_count
    if _storage_dir is not None:
        for name in ("fap_memory.json", "verification.jsonl"):
            try:
                (_storage_dir / name).unlink(missing_ok=True)
            except Exception:
                pass
    _verified_count = 0
    if _runtime is not None:
        if hasattr(_runtime, "memory"):
            try:
                _runtime.memory = []
            except Exception:
                pass
        if hasattr(_runtime, "recent"):
            try:
                _runtime.recent = []
            except Exception:
                pass
    return json.dumps(_status_payload(), ensure_ascii=False)


def _status_payload() -> dict:
    sidecar = f"V{_release_version}" if str(_release_version).isdigit() else str(_release_version)
    status_text = (
        f"READY · {_runtime_name} · release={sidecar} · "
        f"sidecar={'ON' if _autonomy_loaded else 'OFF'} · verified={_verified_count}"
    )
    return {
        "status": status_text,
        "runtime": _runtime_name,
        "release": _release_version,
        "core_source": _core_source,
        "main_sha": _main_sha,
        "autonomy_loaded": _autonomy_loaded,
        "verified": _verified_count,
    }


def status() -> str:
    return json.dumps(_status_payload(), ensure_ascii=False)
