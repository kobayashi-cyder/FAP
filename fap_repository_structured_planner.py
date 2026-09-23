from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from fap_repository_planner import (
    EXPLICIT_PATH,
    PatchPlan,
    PlannedFile,
    RepositoryPlanner,
    _plan_digest,
)


_CREATE_INTENT = re.compile(
    r"(create|new file|add file|make file|作成|生成|新規|新しいファイル|ファイルを追加)",
    re.I,
)
_DELETE_INTENT = re.compile(r"(delete|remove|drop file|削除|消去)", re.I)
_MODIFY_INTENT = re.compile(
    r"(fix|repair|update|modify|change|implement|refactor|edit|修正|変更|更新|実装|改善|編集|直す)",
    re.I,
)


class RepositoryStructuredPlanner(RepositoryPlanner):
    """Planner variant that resolves per-path operations in mixed coding goals.

    The legacy planner intentionally uses broad task-level mutation flags. That
    is conservative, but a request such as "update a.py and create b.md" can be
    rejected because the create verb is applied to every explicit path. This
    planner keeps the same repository reader and PatchPlan contract while
    deriving create/modify/delete intent next to each explicit path.
    """

    VERSION = "fap.repository.structured_plan.v1"

    def plan(self, goal: str) -> PatchPlan:
        base = super().plan(goal)
        goal = str(goal or "").strip()
        hints = _explicit_path_intents(goal)
        if not hints:
            return base

        known_paths = set(self.reader._by_path)
        explicit_paths = set(hints)

        transformed: list[PlannedFile] = []
        seen: set[str] = set()
        for item in base.files:
            hint = hints.get(item.path)
            if hint is None:
                if item.path in explicit_paths:
                    operation = "inspect"
                elif item.operation in {"modify", "delete", "create"}:
                    operation = "inspect"
                else:
                    operation = item.operation
            elif hint == "create":
                operation = "create" if item.path not in known_paths else "inspect"
            elif hint == "delete":
                operation = "delete" if item.path in known_paths else "inspect"
            else:
                operation = "modify" if item.path in known_paths else "inspect"

            if item.path not in seen:
                transformed.append(replace(item, operation=operation))
                seen.add(item.path)

        # The base planner already materializes explicit new paths whenever a
        # create verb exists. Add any path-local create target that did not make
        # that list, while preserving the same max_files boundary.
        for path, hint in hints.items():
            if (
                hint == "create"
                and path not in known_paths
                and path not in seen
                and len(transformed) < self.max_files
            ):
                transformed.append(
                    PlannedFile(
                        path=path,
                        before_sha256="",
                        operation="create",
                        reason="explicit_new_path:structured_intent",
                    )
                )
                seen.add(path)

        risks = [
            flag
            for flag in base.risk_flags
            if flag
            not in {
                "ambiguous_delete_target",
                "explicit_target_missing",
                "create_target_exists",
                "delete_requested",
                "create_requested",
            }
        ]

        if any(op == "delete" for op in hints.values()):
            risks.append("delete_requested")
        if any(op == "create" for op in hints.values()):
            risks.append("create_requested")

        create_existing = sorted(
            path for path, op in hints.items()
            if op == "create" and path in known_paths
        )
        if create_existing:
            risks.append("create_target_exists")

        missing_targets = sorted(
            path for path, op in hints.items()
            if op in {"modify", "delete"} and path not in known_paths
        )
        if missing_targets:
            risks.append("explicit_target_missing")

        files = tuple(transformed)
        risks_tuple = tuple(dict.fromkeys(risks))
        if base.status == "stale_context":
            status = "stale_context"
        elif (
            not files
            or "create_target_exists" in risks_tuple
            or "explicit_target_missing" in risks_tuple
        ):
            status = "insufficient_context"
        else:
            status = "ready"

        plan_id = _plan_digest(
            task=base.task,
            status=status,
            files=files,
            checks=base.required_checks,
            risks=risks_tuple,
        )
        return PatchPlan(
            version=base.version,
            plan_id=plan_id,
            status=status,
            task=base.task,
            files=files,
            required_checks=base.required_checks,
            risk_flags=risks_tuple,
            write_enabled=False,
        )


def _explicit_path_intents(goal: str) -> dict[str, str]:
    matches = list(EXPLICIT_PATH.finditer(str(goal or "")))
    if not matches:
        return {}

    global_ops = _global_operation_set(goal)
    out: dict[str, str] = {}
    previous_op: str | None = None

    for index, match in enumerate(matches):
        path = _normalize_path(match.group(1))
        if not path:
            continue

        left_bound = matches[index - 1].end() if index else 0
        right_bound = matches[index + 1].start() if index + 1 < len(matches) else len(goal)
        left = goal[left_bound:match.start()]
        right = goal[match.end():right_bound]

        left_hit = _nearest_left_intent(left)
        right_hit = _nearest_right_intent(right)
        chosen: str | None = None

        if left_hit and right_hit:
            left_distance, left_op = left_hit
            right_distance, right_op = right_hit
            # Prefer a suffix-style operation on ties. This supports Japanese
            # forms such as "file.pyを削除" while English prefix verbs continue
            # to win whenever they are closer.
            chosen = right_op if right_distance <= left_distance else left_op
        elif left_hit:
            chosen = left_hit[1]
        elif right_hit:
            chosen = right_hit[1]
        elif previous_op is not None:
            chosen = previous_op
        elif len(global_ops) == 1:
            chosen = next(iter(global_ops))

        if chosen is not None:
            out[path] = chosen
            previous_op = chosen

    return out


def _global_operation_set(text: str) -> set[str]:
    ops: set[str] = set()
    if _CREATE_INTENT.search(text):
        ops.add("create")
    if _DELETE_INTENT.search(text):
        ops.add("delete")
    if _MODIFY_INTENT.search(text):
        ops.add("modify")
    return ops


def _nearest_left_intent(text: str) -> tuple[int, str] | None:
    hits = _intent_hits(text)
    if not hits:
        return None
    start, end, op, priority = max(
        hits,
        key=lambda row: (row[1], row[3], row[0]),
    )
    return (len(text) - end, op)


def _nearest_right_intent(text: str) -> tuple[int, str] | None:
    hits = _intent_hits(text)
    if not hits:
        return None
    start, end, op, priority = min(
        hits,
        key=lambda row: (row[0], -row[3], -(row[1] - row[0])),
    )
    return (start, op)


def _intent_hits(text: str) -> list[tuple[int, int, str, int]]:
    hits: list[tuple[int, int, str, int]] = []
    for op, pattern, priority in (
        ("create", _CREATE_INTENT, 3),
        ("delete", _DELETE_INTENT, 3),
        ("modify", _MODIFY_INTENT, 2),
    ):
        for match in pattern.finditer(text):
            hits.append((match.start(), match.end(), op, priority))
    return hits


def _normalize_path(raw: str) -> str:
    value = str(raw or "").replace("\\", "/").lstrip("./")
    parts = Path(value).parts
    if (
        not value
        or value.startswith("/")
        or ".." in parts
        or ".git" in parts
    ):
        return ""
    return value
