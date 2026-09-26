from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
import sys

_runtime = None
_storage_dir: Path | None = None
_packaged_root = Path(__file__).resolve().parent
_runtime_root = _packaged_root
_runtime_source = "packaged"
_runtime_commit = "unknown"
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


def _active_state_path() -> Path:
    if _storage_dir is None:
        raise RuntimeError("FAP storage is not initialized")
    return _storage_dir / "runtime_active.json"


def _read_active_state() -> dict:
    if _storage_dir is None:
        return {}
    path = _active_state_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(value, dict):
        return {}
    slot = str(value.get("slot") or "")
    commit = str(value.get("source_commit") or "")
    if slot not in {"A", "B"}:
        return {}
    root = _storage_dir / "runtime_slots" / slot
    if not (root / "fap_1x_standard_runtime.py").is_file():
        return {}
    value["root"] = str(root)
    value["source_commit"] = commit
    return value


def _select_runtime_root() -> tuple[Path, str, str]:
    state = _read_active_state()
    root = state.get("root")
    if root:
        slot = str(state.get("slot"))
        commit = str(state.get("source_commit") or "unknown")
        return Path(root), f"git:{slot}", commit
    return _packaged_root, "packaged", _main_sha


def _purge_fap_modules() -> None:
    for name in tuple(sys.modules):
        if name.startswith("fap_"):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()


def _prepare_sys_path(root: Path) -> None:
    root_text = str(root.resolve())
    kept = []
    for item in sys.path:
        text = str(item)
        if _storage_dir is not None:
            slots = str((_storage_dir / "runtime_slots").resolve())
            try:
                if str(Path(text).resolve()).startswith(slots):
                    continue
            except Exception:
                pass
        if text == root_text:
            continue
        kept.append(item)
    sys.path[:] = [root_text] + kept


def _build_runtime(root: Path, *, with_memory: bool):
    _prepare_sys_path(root)
    _purge_fap_modules()
    module = importlib.import_module("fap_1x_standard_runtime")
    cls = getattr(module, "FAP1xStandardRuntime")
    memory_root = (_storage_dir / "semantic_memory") if (with_memory and _storage_dir) else None
    return cls(
        root=root,
        memory_root=memory_root,
        max_history_messages=48,
    )


def _load_selected_runtime() -> None:
    global _runtime, _runtime_root, _runtime_source, _runtime_commit
    root, source, commit = _select_runtime_root()
    _runtime = _build_runtime(root, with_memory=True)
    _runtime_root = root
    _runtime_source = source
    _runtime_commit = commit


def initialize(storage_dir: str) -> str:
    global _storage_dir, _verified_count
    _storage_dir = Path(storage_dir)
    _storage_dir.mkdir(parents=True, exist_ok=True)
    (_storage_dir / "runtime_slots").mkdir(parents=True, exist_ok=True)
    _read_meta()
    _load_selected_runtime()

    log_path = _storage_dir / "verification.jsonl"
    if log_path.exists():
        try:
            _verified_count = sum(1 for _ in log_path.open("r", encoding="utf-8"))
        except Exception:
            _verified_count = 0

    return json.dumps(_status_payload(), ensure_ascii=False)


def validate_runtime(root_path: str) -> str:
    root = Path(root_path).resolve()
    if _storage_dir is None:
        raise RuntimeError("FAP storage is not initialized")

    slots_root = (_storage_dir / "runtime_slots").resolve()
    if root.parent != slots_root:
        raise ValueError("runtime candidate must be an A/B slot")
    if root.name not in {"A", "B"}:
        raise ValueError("runtime candidate slot must be A or B")

    entrypoint = root / "fap_1x_standard_runtime.py"
    if not entrypoint.is_file():
        raise FileNotFoundError("runtime entrypoint is missing")

    python_files = sorted(root.glob("fap_*.py"))
    if not python_files:
        raise ValueError("runtime contains no FAP Python modules")

    parsed = 0
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parsed += 1

    knowledge = root / "knowledge"
    knowledge_files = sorted(knowledge.rglob("*.jsonl")) if knowledge.is_dir() else []
    for path in knowledge_files:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except Exception as exc:
                raise ValueError(f"invalid JSONL: {path.name}:{line_no}") from exc

    candidate = _build_runtime(root, with_memory=False)
    status = candidate.status()
    if str(status.get("version") or "") != "1.0.01":
        raise ValueError("candidate runtime version mismatch")

    # Deterministic smoke path which must not depend on network access.
    result = candidate.run_turn("真空中の光速は？", session_id="ota-smoke")
    if str(result.state) != "handled":
        raise ValueError("candidate runtime failed deterministic smoke test")

    return json.dumps(
        {
            "ok": True,
            "python_files": parsed,
            "knowledge_files": len(knowledge_files),
            "endpoint_count": len(candidate.fabric.endpoint_ids),
            "version": status.get("version"),
        },
        ensure_ascii=False,
    )


def reload_runtime() -> str:
    _load_selected_runtime()
    return json.dumps(_status_payload(), ensure_ascii=False)


def _restore_agent_history(recent_log_json: str, query: str) -> tuple[dict, ...]:
    try:
        rows = json.loads(str(recent_log_json or "[]"))
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []

    history: list[dict] = []
    for row in rows[-64:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        history.append(
            {
                "role": role,
                "content": text[:20000],
                "text": text[:20000],
                "channel": str(row.get("channel") or "chat")[:40],
            }
        )

    # The durable log normally already contains the just-submitted user turn.
    # run_turn will append that turn itself, so avoid duplicating it.
    clean_query = str(query or "").strip()
    if history and history[-1].get("role") == "user":
        tail = str(history[-1].get("text") or "").strip()
        if tail == clean_query:
            history.pop()

    return tuple(history[-48:])


def run_agent(query: str, recent_log_json: str = "[]", source_channel: str = "agent") -> str:
    if _runtime is None:
        raise RuntimeError("FAP 1.x runtime is not initialized")

    sid = "android-agent"
    restored = list(_restore_agent_history(recent_log_json, query))
    try:
        _runtime._histories[sid] = restored
    except Exception:
        pass

    result = _runtime.run_turn(
        str(query),
        session_id=sid,
        channel="chat",
        metadata={
            "source_channel": str(source_channel or "agent")[:40],
            "durable_chat_log": True,
        },
    )
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
            "needs_teacher": bool(payload.get("needs_teacher", False)),
            "status": _status_payload()["status"],
        },
        ensure_ascii=False,
    )


def run(query: str) -> str:
    return run_agent(query, "[]", "legacy")


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
        "runtime_source": _runtime_source,
        "runtime_commit": _runtime_commit,
    }
    with (_storage_dir / "verification.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    _verified_count += 1
    return json.dumps(_status_payload(), ensure_ascii=False)


def clear() -> str:
    global _verified_count
    if _storage_dir is not None:
        try:
            (_storage_dir / "verification.jsonl").unlink(missing_ok=True)
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

    short_commit = _runtime_commit[:10] if _runtime_commit else "unknown"
    return {
        "status": (
            f"READY · FAP 1.0.01 Pixel · endpoints={endpoint_count} · "
            f"memory={'ON' if memory_on else 'OFF'} · verified={_verified_count} · "
            f"source={_runtime_source}@{short_commit}"
        ),
        "runtime": "FAP1xStandardRuntime",
        "release": _release_version,
        "main_sha": _main_sha,
        "runtime_source": _runtime_source,
        "runtime_commit": _runtime_commit,
        "runtime_root": str(_runtime_root),
        "verified": _verified_count,
        "pixel_browser": True,
        "git_ota": True,
    }


def status() -> str:
    return json.dumps(_status_payload(), ensure_ascii=False)
