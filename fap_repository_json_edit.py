from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


class JsonEditError(RuntimeError):
    pass


@dataclass(frozen=True)
class JsonSetSpec:
    path: str
    keys: tuple[str, ...]
    value: Any


@dataclass(frozen=True)
class JsonDeleteSpec:
    path: str
    keys: tuple[str, ...]


JsonSpec = JsonSetSpec | JsonDeleteSpec


class RepositoryJsonEditor:
    """Semantic JSON editor with plan/hash preconditions and strict parsing."""

    VERSION = "fap.repository.json_edit.v1"

    def build_edit(self, root: str | Path, plan: PatchPlan, specs: Iterable[JsonSpec], *, indent: int = 2) -> FileEdit:
        rows = tuple(specs)
        if not rows:
            raise JsonEditError("at least one JSON edit spec is required")
        paths = {row.path for row in rows}
        if len(paths) != 1:
            raise JsonEditError("one JSON edit build may target only one file")
        path = next(iter(paths))
        if not path.endswith(".json"):
            raise JsonEditError("JSON editor requires a .json path")
        if not 0 <= int(indent) <= 8:
            raise JsonEditError("indent must be in [0, 8]")

        planned = next((item for item in plan.files if item.path == path), None)
        if planned is None or planned.operation not in {"modify", "create"}:
            raise JsonEditError("JSON path is not a planned modify/create")

        root_path = Path(root).expanduser().resolve()
        full = root_path / path
        try:
            full.resolve().relative_to(root_path)
        except ValueError as exc:
            raise JsonEditError("JSON path escapes repository root") from exc

        if planned.operation == "create":
            if full.exists() or full.is_symlink():
                raise JsonEditError("create target already exists")
            document: Any = {}
        else:
            if not full.is_file() or full.is_symlink():
                raise JsonEditError("JSON source unavailable")
            raw = full.read_bytes()
            if sha256(raw).hexdigest() != planned.before_sha256:
                raise JsonEditError("STALE_PLAN: JSON source hash changed")
            try:
                document = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant)
            except (UnicodeDecodeError, json.JSONDecodeError, JsonEditError) as exc:
                raise JsonEditError("JSON source is invalid or ambiguous") from exc

        if not isinstance(document, dict):
            raise JsonEditError("JSON root must be an object")

        for spec in rows:
            keys = _keys(spec.keys)
            if isinstance(spec, JsonSetSpec):
                _set_path(document, keys, spec.value)
            elif isinstance(spec, JsonDeleteSpec):
                _delete_path(document, keys)
            else:
                raise JsonEditError("unsupported JSON edit spec")

        try:
            content = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=int(indent), allow_nan=False) + "\n"
            content.encode("utf-8", errors="strict")
            json.loads(content, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
        except (TypeError, ValueError, UnicodeEncodeError, json.JSONDecodeError, JsonEditError) as exc:
            raise JsonEditError("JSON result is not strictly serializable") from exc
        return FileEdit(path=path, operation=planned.operation, before_sha256=planned.before_sha256, content=content)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise JsonEditError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _reject_constant(value: str) -> Any:
    raise JsonEditError(f"non-finite JSON number: {value}")


def _keys(raw: Iterable[str]) -> tuple[str, ...]:
    keys = tuple(str(x) for x in raw)
    if not keys:
        raise JsonEditError("JSON key path must be non-empty")
    return keys


def _set_path(document: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    cursor = document
    for key in keys[:-1]:
        if key not in cursor:
            cursor[key] = {}
        current = cursor[key]
        if not isinstance(current, dict):
            raise JsonEditError(f"intermediate key is not an object: {key}")
        cursor = current
    cursor[keys[-1]] = value


def _delete_path(document: dict[str, Any], keys: tuple[str, ...]) -> None:
    cursor = document
    for key in keys[:-1]:
        current = cursor.get(key)
        if not isinstance(current, dict):
            raise JsonEditError(f"delete path not found: {'.'.join(keys)}")
        cursor = current
    if keys[-1] not in cursor:
        raise JsonEditError(f"delete path not found: {'.'.join(keys)}")
    del cursor[keys[-1]]
