from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

from fap_repository_planner import RepositoryPlanner


_SAFE_BRANCH = re.compile(r"^[0-9A-Za-z._/-]{1,200}$")


@dataclass(frozen=True)
class CollaborationFile:
    path: str
    operation: str
    before_sha256: str
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryCollaborationSnapshot:
    contract: str
    goal: str
    branch: str
    base_commit: str
    plan_id: str
    plan_status: str
    repository_digest: str
    files: tuple[CollaborationFile, ...]
    required_checks: tuple[str, ...]
    risk_flags: tuple[str, ...]
    omitted_files: int
    index_errors: tuple[str, ...]
    write_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryCodingCollaboration:
    """Read-only handoff surface for parallel chats or coding agents.

    The snapshot intentionally contains plan metadata and hashes but no source
    excerpts, generated code, provider output or secrets. It is suitable for a
    second agent to decide what to inspect next while all writes still flow
    through the normal repository coding pipeline.
    """

    CONTRACT = "fap.repository.collab.v1"

    def __init__(
        self,
        root: str | Path,
        *,
        max_files: int = 12,
        max_source_bytes: int = 240_000,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        self.planner = RepositoryPlanner(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
        )

    def snapshot(
        self,
        goal: str,
        *,
        branch: str,
        base_commit: str = "",
    ) -> RepositoryCollaborationSnapshot:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        branch = _safe_collaboration_branch(branch)
        base_commit = str(base_commit or "").strip()
        if base_commit and not re.fullmatch(r"[0-9a-fA-F]{7,64}", base_commit):
            raise ValueError("base_commit must be an abbreviated or full hex commit")

        plan = self.planner.plan(goal)
        context = self.planner.reader.read(goal)
        if context.repository_digest != plan.task.repository_digest:
            raise RuntimeError("planner_context_digest_mismatch")

        files = tuple(
            CollaborationFile(
                path=item.path,
                operation=item.operation,
                before_sha256=item.before_sha256,
                symbols=item.symbols,
            )
            for item in plan.files
        )
        return RepositoryCollaborationSnapshot(
            contract=self.CONTRACT,
            goal=goal,
            branch=branch,
            base_commit=base_commit,
            plan_id=plan.plan_id,
            plan_status=plan.status,
            repository_digest=plan.task.repository_digest,
            files=files,
            required_checks=plan.required_checks,
            risk_flags=plan.risk_flags,
            omitted_files=context.omitted_files,
            index_errors=context.index_errors,
            write_enabled=False,
        )


def _safe_collaboration_branch(raw: str) -> str:
    value = str(raw or "").strip()
    if not _SAFE_BRANCH.fullmatch(value):
        raise ValueError("branch contains invalid characters")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise ValueError("branch shape is invalid")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("branch shape is invalid")
    if value.casefold() in {"main", "master"}:
        raise ValueError("collaboration snapshots require a non-main branch")
    return value
