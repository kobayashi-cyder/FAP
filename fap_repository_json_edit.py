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
    """Semantic JSON config editor with plan/hash preconditions."""

    VERSION = "fap.repository.json_edit.v1"

    def build_edit(
        self,
        root: str | Path,
        plan: PatchPlan,
        specs: Iterable[JsonSpec],
        *,
        indent: int = 2,
    ) -> FileEdit:
        rows = tuple(specs)
        if not rows:
            raise JsonEditError("at least one JSON edit spec is required")
        paths = {row.path for row in rows}
        if len(paths) != 1:
            raise JsonEditError("one JSON edit build may target only one file")
        path = next(iter(paths))
        if not path.endswith(".json"):
            raise JsonEditError("JSON editor requires a .json path")

        planned = next((item for item in plan.files if item.path == path), None)
        if planned is None or planned.operation not in {"modify", "create"}:
            raise JsonEditError("JSON path is not a planned modify/create")

        root_path = Path(root).expanduser().resolve()
        full = root_path / path
        if planned.operation == "create":
            if full.exists():
                raise JsonEditError("create target already exists")
            document: Any = {}
        else:
            if not full.is_file() or full.is_symlink():
                raise JsonEditError("JSON source unavailable")
            raw = full.read_bytes()
            if sha256(raw).hexdigest() != planned.before_sha256:
                raise JsonEditError("STALE_PLAN: JSON source hash changed")
            try:
                document = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise JsonEditError("JSON source is invalid") from exc

        if not isinstance(document, dict):
            raise JsonEditError("JSON root must be an object")

        for spec in rows:
            keys = _keys(spec.keys)
            if isinstance(spec, JsonSetSpec):
                _set_path(document, keys, spec.value)
            else:
                _delete_path(document, keys)

        content = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=int(indent),
        ) + "\n"
        # Parse the result again so serialization bugs fail before FileEdit.
        json.loads(content)
        return FileEdit(
            path=path,
            operation=planned.operation,
            before_sha256=planned.before_sha256,
            content=content,
        )


def _keys(raw: Iterable[str]) -> tuple[str, ...]:
    keys = tuple(str(x) for x in raw)
    if not keys or any(not x or x in {".", ".."} for x in keys):
        raise JsonEditError("JSON key path must be non-empty")
    return keys


def _set_path(document: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    cursor = document
    for key in keys[:-1]:
        current = cursor.get(key)
        if current is None:
            current = {}
            cursor[key] = current
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
