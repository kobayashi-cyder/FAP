from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re

from fap_repository_reader import RepositoryReader


MUTATE_WORDS = re.compile(
    r"(fix|repair|update|modify|change|implement|refactor|add|修正|変更|更新|実装|改善|追加)",
    re.I,
)
DELETE_WORDS = re.compile(r"(delete|remove|削除|消去)", re.I)
CREATE_WORDS = re.compile(r"(create|new file|add file|新規|新しいファイル|ファイルを追加)", re.I)
EXPLICIT_PATH = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.(?:py|md|json|jsonl|toml|ya?ml|html|css|js|ts|tsx|jsx|sh|ps1|cmd))(?![A-Za-z0-9_./-])",
    re.I,
)


@dataclass(frozen=True)
class RepositoryTask:
    goal: str
    repository_digest: str
    max_files: int
    max_source_bytes: int


@dataclass(frozen=True)
class PlannedFile:
    path: str
    before_sha256: str
    operation: str
    reason: str
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class PatchPlan:
    version: str
    plan_id: str
    status: str
    task: RepositoryTask
    files: tuple[PlannedFile, ...]
    required_checks: tuple[str, ...]
    risk_flags: tuple[str, ...]
    write_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryPlanner:
    """V87.66 deterministic read-only repository patch planner.

    It may inspect and propose files/operations, but deliberately contains no
    patch application, subprocess, git mutation or filesystem-write capability.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        max_files: int = 8,
        max_source_bytes: int = 120_000,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_files = int(max_files)
        self.max_source_bytes = int(max_source_bytes)
        self.reader = RepositoryReader(
            self.root,
            max_files=self.max_files,
            max_total_bytes=self.max_source_bytes,
        )

    def plan(
        self,
        goal: str,
        *,
        preferred_paths: tuple[str, ...] = (),
    ) -> PatchPlan:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        context = self.reader.read(
            goal,
            preferred_paths=preferred_paths,
        )
        stale = any(item.stale for item in context.files)

        mutation = bool(MUTATE_WORDS.search(goal))
        delete = bool(DELETE_WORDS.search(goal))
        create = bool(CREATE_WORDS.search(goal))
        known_paths = set(self.reader._by_path)
        explicit_paths = set(_explicit_paths(goal))
        explicit_existing = explicit_paths & known_paths
        preferred_existing = {
            str(path).strip().replace("\\", "/")
            for path in preferred_paths
        } & known_paths

        files: list[PlannedFile] = []
        goal_tokens = _goal_tokens(goal)
        for item in context.files:
            rec = self.reader._by_path[item.path]
            symbols = tuple(
                sym.name for sym in rec.symbols
                if any(token in sym.name.casefold() for token in goal_tokens)
            )[:8]
            dependency_only = bool(item.reasons) and all(
                reason.startswith("dependency_hop:")
                for reason in item.reasons
            )
            if delete:
                operation = (
                    "delete"
                    if item.path in explicit_existing
                    else "inspect"
                )
            elif mutation:
                if explicit_existing:
                    operation = (
                        "modify"
                        if item.path in explicit_existing
                        else "inspect"
                    )
                elif preferred_existing:
                    # In a short multi-turn coding follow-up, keep the previous
                    # repository targets authoritative while treating newly
                    # retrieved files (for example tests mentioned by the
                    # follow-up text) as context-only. Explicit current-turn
                    # paths still take precedence above.
                    operation = (
                        "modify"
                        if item.path in preferred_existing
                        else "inspect"
                    )
                else:
                    operation = "inspect" if dependency_only else "modify"
            else:
                operation = "inspect"
            files.append(
                PlannedFile(
                    path=item.path,
                    before_sha256=item.sha256,
                    operation=operation,
                    reason=", ".join(item.reasons) or "selected_by_reader",
                    symbols=symbols,
                )
            )

        existing = {f.path for f in files}
        if create:
            for path in _explicit_new_paths(goal):
                if path not in known_paths and path not in existing and len(files) < self.max_files:
                    files.append(
                        PlannedFile(
                            path=path,
                            before_sha256="",
                            operation="create",
                            reason="explicit_new_path",
                        )
                    )
                    existing.add(path)

        risks: list[str] = []
        if context.index_errors:
            risks.append("repository_index_errors")
        if stale:
            risks.append("stale_context")
        if delete:
            risks.append("delete_requested")
            if not any(f.operation == "delete" for f in files):
                risks.append("ambiguous_delete_target")
        if (
            mutation
            and explicit_paths
            and not explicit_existing
            and not create
        ):
            risks.append("explicit_target_missing")
        if create and (explicit_paths & known_paths):
            risks.append("create_target_exists")
        if any(f.operation == "create" for f in files):
            risks.append("create_requested")
        if len(files) > 4:
            risks.append("broad_change")
        if any(f.path.startswith(".github/") for f in files):
            risks.append("ci_configuration_touched")

        checks = ["sha_precondition", "sandbox_only"]
        languages = {
            self.reader._by_path[f.path].language
            for f in files if f.path in self.reader._by_path
        }
        if any(f.path.endswith(".py") for f in files):
            languages.add("python")
        if "python" in languages:
            checks.extend(["python_compile", "focused_tests"])
        mutating_ops = any(
            f.operation in {"modify", "create", "delete"}
            for f in files
        )
        if mutating_ops:
            checks.append("regression_tests")
        checks.append("no_direct_main_write")

        if stale:
            status = "stale_context"
        elif (
            not files
            or "ambiguous_delete_target" in risks
            or "explicit_target_missing" in risks
            or "create_target_exists" in risks
        ):
            status = "insufficient_context"
        else:
            status = "ready"

        task = RepositoryTask(
            goal=goal,
            repository_digest=context.repository_digest,
            max_files=self.max_files,
            max_source_bytes=self.max_source_bytes,
        )
        checks_tuple = tuple(dict.fromkeys(checks))
        risks_tuple = tuple(dict.fromkeys(risks))
        files_tuple = tuple(files)
        plan_id = _plan_digest(
            task=task,
            status=status,
            files=files_tuple,
            checks=checks_tuple,
            risks=risks_tuple,
        )
        return PatchPlan(
            version="fap.repository.plan.v1",
            plan_id=plan_id,
            status=status,
            task=task,
            files=files_tuple,
            required_checks=checks_tuple,
            risk_flags=risks_tuple,
            write_enabled=False,
        )


def _plan_digest(
    *,
    task: RepositoryTask,
    status: str,
    files: tuple[PlannedFile, ...],
    checks: tuple[str, ...],
    risks: tuple[str, ...],
) -> str:
    payload = {
        "task": asdict(task),
        "status": status,
        "files": [asdict(x) for x in files],
        "checks": checks,
        "risks": risks,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _explicit_paths(goal: str) -> tuple[str, ...]:
    out = []
    for match in EXPLICIT_PATH.findall(goal):
        path = match.replace("\\", "/").lstrip("./")
        parts = Path(path).parts
        if (
            path
            and not path.startswith("/")
            and ".." not in parts
            and ".git" not in parts
        ):
            out.append(path)
    return tuple(dict.fromkeys(out))


def _explicit_new_paths(goal: str) -> tuple[str, ...]:
    return _explicit_paths(goal)


def _goal_tokens(goal: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[0-9a-z_]{2,}", goal.casefold())))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FAP V87.66 read-only repository planner")
    parser.add_argument("goal")
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-files", type=int, default=8)
    parser.add_argument("--max-source-bytes", type=int, default=120_000)
    args = parser.parse_args(argv)
    planner = RepositoryPlanner(
        args.root,
        max_files=args.max_files,
        max_source_bytes=args.max_source_bytes,
    )
    print(json.dumps(planner.plan(args.goal).to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
