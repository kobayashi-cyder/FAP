from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import Iterable

from fap_repository_planner import PatchPlan
from fap_repository_reader import RepositoryReader


ALLOWED_OPERATIONS = frozenset({"create", "modify", "delete"})


@dataclass(frozen=True)
class FileEdit:
    path: str
    operation: str
    before_sha256: str
    content: str | None = None


@dataclass(frozen=True)
class AppliedFile:
    path: str
    operation: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True)
class ExecutionReport:
    version: str
    plan_id: str
    base_commit: str
    state: str
    files: tuple[AppliedFile, ...]
    diff: str
    diff_truncated: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class SandboxSession:
    """One detached Git worktree used only for a single planned patch candidate."""

    def __init__(
        self,
        executor: "RepositoryPatchExecutor",
        path: Path,
        temp_parent: Path,
        plan: PatchPlan,
        base_commit: str,
    ) -> None:
        self.executor = executor
        self.path = path
        self.temp_parent = temp_parent
        self.plan = plan
        self.base_commit = base_commit
        self.closed = False
        self.applied = False

    def apply(self, edits: Iterable[FileEdit]) -> ExecutionReport:
        if self.closed:
            raise RuntimeError("sandbox session is closed")
        if self.applied:
            raise RuntimeError("sandbox session accepts one patch candidate")
        self.applied = True
        try:
            return self.executor._apply_in_session(self, tuple(edits))
        except Exception as exc:
            return ExecutionReport(
                version="fap.repository.execution.v1",
                plan_id=self.plan.plan_id,
                base_commit=self.base_commit,
                state="rejected",
                files=(),
                diff="",
                diff_truncated=False,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.executor._git(
                self.executor.root,
                "worktree", "remove", "--force", str(self.path),
                timeout=self.executor.git_timeout_sec,
            )
        finally:
            shutil.rmtree(self.temp_parent, ignore_errors=True)

    def __enter__(self) -> "SandboxSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class RepositoryPatchExecutor:
    """V87.67 worktree-only patch executor.

    The source repository working tree is never edited. Candidate writes happen
    only in a detached temporary Git worktree created from the current HEAD.
    Every planned source file is freshness-checked before the worktree is opened,
    and every edit repeats its SHA-256 precondition inside the sandbox.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        max_files: int = 8,
        max_edit_bytes: int = 1_000_000,
        max_total_edit_bytes: int = 2_000_000,
        max_diff_bytes: int = 200_000,
        git_timeout_sec: int = 30,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.root}")
        if not 1 <= int(max_files) <= 32:
            raise ValueError("max_files must be in [1, 32]")
        if int(max_edit_bytes) <= 0 or int(max_total_edit_bytes) <= 0:
            raise ValueError("edit byte limits must be positive")
        if int(max_diff_bytes) <= 0:
            raise ValueError("max_diff_bytes must be positive")
        if not 1 <= int(git_timeout_sec) <= 120:
            raise ValueError("git_timeout_sec must be in [1, 120]")
        self.max_files = int(max_files)
        self.max_edit_bytes = int(max_edit_bytes)
        self.max_total_edit_bytes = int(max_total_edit_bytes)
        self.max_diff_bytes = int(max_diff_bytes)
        self.git_timeout_sec = int(git_timeout_sec)
        self._assert_git_repository()

    def open(self, plan: PatchPlan) -> SandboxSession:
        self._validate_plan(plan)
        base_commit = self._git(
            self.root, "rev-parse", "--verify", "HEAD",
            timeout=self.git_timeout_sec,
        ).stdout.strip()
        if len(base_commit) < 7:
            raise RuntimeError("could not resolve repository HEAD")

        temp_parent = Path(tempfile.mkdtemp(prefix="fap-v8767-")).resolve()
        worktree = temp_parent / "worktree"
        try:
            self._git(
                self.root,
                "worktree", "add", "--detach", str(worktree), base_commit,
                timeout=self.git_timeout_sec,
            )
            self._validate_sandbox_matches_plan(worktree, plan)
            return SandboxSession(self, worktree, temp_parent, plan, base_commit)
        except Exception:
            try:
                if worktree.exists():
                    self._git(
                        self.root,
                        "worktree", "remove", "--force", str(worktree),
                        timeout=self.git_timeout_sec,
                    )
            finally:
                shutil.rmtree(temp_parent, ignore_errors=True)
            raise

    def execute(self, plan: PatchPlan, edits: Iterable[FileEdit]) -> ExecutionReport:
        """Apply once, capture a bounded diff, then always remove the worktree."""
        with self.open(plan) as session:
            return session.apply(tuple(edits))

    def _validate_plan(self, plan: PatchPlan) -> None:
        if plan.version != "fap.repository.plan.v1":
            raise ValueError(f"unsupported plan version: {plan.version}")
        if plan.status != "ready":
            raise ValueError(f"plan is not executable: {plan.status}")
        if len(plan.files) > self.max_files:
            raise ValueError("plan exceeds executor file limit")

        current = RepositoryReader(
            self.root,
            max_files=max(1, min(self.max_files, 32)),
            max_total_bytes=1,
            max_file_bytes=1,
            dependency_hops=0,
        )
        if current.repository_digest != plan.task.repository_digest:
            raise ValueError("STALE_PLAN: repository digest changed")

        seen: set[str] = set()
        for planned in plan.files:
            rel = _safe_relative_path(planned.path)
            if rel in seen:
                raise ValueError(f"duplicate planned path: {rel}")
            seen.add(rel)
            path = self.root / rel
            if planned.operation == "create":
                if planned.before_sha256:
                    raise ValueError(f"create plan must not have before hash: {rel}")
                if path.exists() or path.is_symlink():
                    raise ValueError(f"STALE_PLAN: create target already exists: {rel}")
                continue
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"STALE_PLAN: planned file unavailable: {rel}")
            actual = _sha256_file(path)
            if actual != planned.before_sha256:
                raise ValueError(f"STALE_PLAN: file hash changed: {rel}")

    def _validate_sandbox_matches_plan(self, worktree: Path, plan: PatchPlan) -> None:
        for planned in plan.files:
            rel = _safe_relative_path(planned.path)
            path = worktree / rel
            if planned.operation == "create":
                if path.exists() or path.is_symlink():
                    raise ValueError(f"sandbox create target already exists: {rel}")
                continue
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"sandbox source unavailable: {rel}")
            if _sha256_file(path) != planned.before_sha256:
                raise ValueError(
                    f"plan was not produced from HEAD content: {rel}"
                )

    def _apply_in_session(
        self,
        session: SandboxSession,
        edits: tuple[FileEdit, ...],
    ) -> ExecutionReport:
        if not edits:
            raise ValueError("at least one edit is required")
        if len(edits) > self.max_files:
            raise ValueError("edit set exceeds executor file limit")

        planned = {item.path: item for item in session.plan.files}
        normalized: list[tuple[FileEdit, str]] = []
        seen: set[str] = set()
        total_bytes = 0
        for edit in edits:
            rel = _safe_relative_path(edit.path)
            if rel in seen:
                raise ValueError(f"duplicate edit path: {rel}")
            seen.add(rel)
            if rel not in planned:
                raise ValueError(f"edit path is not present in plan: {rel}")
            if edit.operation not in ALLOWED_OPERATIONS:
                raise ValueError(f"unsupported edit operation: {edit.operation}")
            if edit.operation != planned[rel].operation:
                raise ValueError(
                    f"operation differs from plan for {rel}: "
                    f"{edit.operation} != {planned[rel].operation}"
                )
            if edit.before_sha256 != planned[rel].before_sha256:
                raise ValueError(f"edit before hash differs from plan: {rel}")

            if edit.operation in {"create", "modify"}:
                if edit.content is None:
                    raise ValueError(f"content is required for {edit.operation}: {rel}")
                size = len(edit.content.encode("utf-8"))
                if size > self.max_edit_bytes:
                    raise ValueError(f"edit exceeds per-file byte limit: {rel}")
                total_bytes += size
            elif edit.content is not None:
                raise ValueError(f"delete edit must not contain content: {rel}")
            normalized.append((edit, rel))

        if total_bytes > self.max_total_edit_bytes:
            raise ValueError("edit set exceeds total byte limit")

        applied: list[AppliedFile] = []
        for edit, rel in normalized:
            target = session.path / rel
            _reject_symlink_chain(session.path, rel)

            if edit.operation == "create":
                if target.exists() or target.is_symlink():
                    raise ValueError(f"create target already exists: {rel}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(edit.content or "", encoding="utf-8", newline="")
                after = _sha256_file(target)
            elif edit.operation == "modify":
                if not target.is_file() or target.is_symlink():
                    raise ValueError(f"modify target unavailable: {rel}")
                actual = _sha256_file(target)
                if actual != edit.before_sha256:
                    raise ValueError(f"STALE_PLAN: sandbox file changed: {rel}")
                target.write_text(edit.content or "", encoding="utf-8", newline="")
                after = _sha256_file(target)
            else:
                if not target.is_file() or target.is_symlink():
                    raise ValueError(f"delete target unavailable: {rel}")
                actual = _sha256_file(target)
                if actual != edit.before_sha256:
                    raise ValueError(f"STALE_PLAN: sandbox file changed: {rel}")
                target.unlink()
                after = ""

            applied.append(
                AppliedFile(
                    path=rel,
                    operation=edit.operation,
                    before_sha256=edit.before_sha256,
                    after_sha256=after,
                )
            )

        check = self._git(
            session.path, "diff", "--check", "--",
            timeout=self.git_timeout_sec,
            check=False,
        )
        diff_proc = self._git(
            session.path, "diff", "--no-ext-diff", "--unified=3", "--",
            timeout=self.git_timeout_sec,
            check=False,
        )
        diff, truncated = _bounded_text(diff_proc.stdout, self.max_diff_bytes)
        errors: list[str] = []
        if check.returncode != 0:
            errors.append("git_diff_check_failed")
            if check.stdout.strip():
                detail, _ = _bounded_text(check.stdout, 20_000)
                errors.append(detail.strip())
        if diff_proc.returncode != 0:
            errors.append("git_diff_failed")
        state = "applied_in_sandbox" if not errors else "rejected"

        return ExecutionReport(
            version="fap.repository.execution.v1",
            plan_id=session.plan.plan_id,
            base_commit=session.base_commit,
            state=state,
            files=tuple(applied),
            diff=diff,
            diff_truncated=truncated,
            errors=tuple(errors),
        )

    def _assert_git_repository(self) -> None:
        proc = self._git(
            self.root,
            "rev-parse", "--is-inside-work-tree",
            timeout=self.git_timeout_sec,
            check=False,
        )
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            raise ValueError(f"not a Git working tree: {self.root}")

    @staticmethod
    def _git(
        cwd: Path,
        *args: str,
        timeout: int,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            shell=False,
        )
        if check and proc.returncode != 0:
            message, _ = _bounded_text(proc.stdout, 20_000)
            raise RuntimeError(
                f"git {' '.join(args)} failed with {proc.returncode}: {message.strip()}"
            )
        return proc


def _safe_relative_path(raw: str) -> str:
    text = str(raw or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute():
        raise ValueError(f"unsafe path: {raw!r}")
    if any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise ValueError(f"unsafe path: {raw!r}")
    normalized = path.as_posix()
    if normalized.startswith(".git/"):
        raise ValueError(f"unsafe path: {raw!r}")
    return normalized


def _reject_symlink_chain(root: Path, rel: str) -> None:
    current = root
    parts = PurePosixPath(rel).parts
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink path component rejected: {rel}")
        if not current.exists():
            break
    resolved_parent = (root / rel).parent.resolve()
    try:
        resolved_parent.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes sandbox: {rel}") from exc


def _sha256_file(path: Path, chunk_size: int = 128 * 1024) -> str:
    h = sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _bounded_text(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text, False
    clipped = raw[:max_bytes]
    while clipped:
        try:
            decoded = clipped.decode("utf-8")
            return decoded + "\n...<truncated>\n", True
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return "...<truncated>\n", True
