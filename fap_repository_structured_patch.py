from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
from typing import Callable, Iterable

from fap_repository_ast_patch import ASTPatchSpec, RepositoryASTFunctionPatcher
from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan
from fap_repository_python_symbol_edit import (
    PythonSymbolRenameError,
    PythonSymbolRenameSpec,
    RepositoryPythonTopLevelRenamer,
)
from fap_repository_reader import RepositoryReadContext
from fap_repository_shell_edit import (
    RepositoryShellBlockEditor,
    ShellBlockEditError,
    ShellBlockSpec,
)
from fap_repository_verifier import CandidateAttempt


class StructuredPatchError(RuntimeError):
    """Raised when declarative repository edits cannot be compiled safely."""


@dataclass(frozen=True)
class ExactReplaceSpec:
    path: str
    old: str
    new: str
    expected_count: int = 1


@dataclass(frozen=True)
class CreateTextSpec:
    path: str
    content: str


@dataclass(frozen=True)
class DeleteFileSpec:
    path: str


StructuredSpec = (
    ASTPatchSpec
    | PythonSymbolRenameSpec
    | ShellBlockSpec
    | ExactReplaceSpec
    | CreateTextSpec
    | DeleteFileSpec
)
StructuredSpecInput = StructuredSpec | Mapping[str, object]

StructuredSpecProvider = Callable[
    [PatchPlan, RepositoryReadContext],
    Iterable[StructuredSpecInput],
]
StructuredRepairSpecProvider = Callable[
    [tuple[FileEdit, ...], CandidateAttempt],
    Iterable[StructuredSpecInput] | None,
]


_SAFE_SEGMENT = re.compile(r"^[0-9A-Za-z_.-]+$")
_SAFE_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def structured_spec_from_mapping(row: Mapping[str, object]) -> StructuredSpec:
    """Parse a provider-neutral JSON-like edit row into a typed spec."""
    if not isinstance(row, Mapping):
        raise TypeError("structured spec row must be a mapping")
    op = str(row.get("op") or "").strip().casefold()
    path = str(row.get("path") or "").strip()

    if op == "python_function_body":
        symbol = str(row.get("target_symbol") or "").strip()
        body = str(row.get("replacement_body") or "")
        if not _SAFE_SYMBOL.fullmatch(symbol):
            raise StructuredPatchError("target_symbol is invalid")
        return ASTPatchSpec(path=path, target_symbol=symbol, replacement_body=body)

    if op == "python_symbol_rename":
        old_name = str(row.get("old_name") or "").strip()
        new_name = str(row.get("new_name") or "").strip()
        if (
            not _SAFE_IDENTIFIER.fullmatch(old_name)
            or not _SAFE_IDENTIFIER.fullmatch(new_name)
            or old_name == new_name
        ):
            raise StructuredPatchError("python symbol rename names are invalid")
        return PythonSymbolRenameSpec(
            path=path,
            old_name=old_name,
            new_name=new_name,
        )

    if op == "shell_block":
        name = str(row.get("name") or "").strip()
        body = str(row.get("body") or "")
        return ShellBlockSpec(
            path=path,
            name=name,
            body=body,
        )

    if op == "replace_exact":
        try:
            expected_count = int(row.get("expected_count", 1))
        except (TypeError, ValueError, OverflowError) as exc:
            raise StructuredPatchError("expected_count must be an integer") from exc
        return ExactReplaceSpec(
            path=path,
            old=str(row.get("old") or ""),
            new=str(row.get("new") or ""),
            expected_count=expected_count,
        )

    if op == "create_text":
        return CreateTextSpec(
            path=path,
            content=str(row.get("content") or ""),
        )

    if op == "delete_file":
        return DeleteFileSpec(path=path)

    raise StructuredPatchError(f"unsupported structured patch op: {op or '<empty>'}")


def structured_spec_to_dict(spec: StructuredSpecInput) -> dict:
    """Serialize a typed spec into the stable cross-agent row contract."""
    typed = _coerce_spec(spec)
    if isinstance(typed, ASTPatchSpec):
        return {
            "op": "python_function_body",
            "path": typed.path,
            "target_symbol": typed.target_symbol,
            "replacement_body": typed.replacement_body,
        }
    if isinstance(typed, PythonSymbolRenameSpec):
        return {
            "op": "python_symbol_rename",
            "path": typed.path,
            "old_name": typed.old_name,
            "new_name": typed.new_name,
        }
    if isinstance(typed, ShellBlockSpec):
        return {
            "op": "shell_block",
            "path": typed.path,
            "name": typed.name,
            "body": typed.body,
        }
    if isinstance(typed, ExactReplaceSpec):
        return {
            "op": "replace_exact",
            "path": typed.path,
            "old": typed.old,
            "new": typed.new,
            "expected_count": typed.expected_count,
        }
    if isinstance(typed, CreateTextSpec):
        return {
            "op": "create_text",
            "path": typed.path,
            "content": typed.content,
        }
    if isinstance(typed, DeleteFileSpec):
        return {"op": "delete_file", "path": typed.path}
    raise AssertionError("unreachable structured spec type")


class RepositoryStructuredProposalProvider:
    """Compile bounded declarative edits into the existing FileEdit boundary.

    This expands repository coding without bypassing the existing planner,
    detached-worktree executor or verifier. Multiple operations may target one
    planned file: exact replacements and Python function-body patches are
    composed in memory and emitted as one final FileEdit with the original plan
    hash as its precondition.
    """

    VERSION = "fap.repository.structured_patch.v1"

    def __init__(
        self,
        root: str | Path,
        provider: StructuredSpecProvider,
        *,
        max_operations: int = 16,
        max_source_bytes: int = 1_000_000,
        max_total_output_bytes: int = 2_000_000,
        patcher: RepositoryASTFunctionPatcher | None = None,
        renamer: RepositoryPythonTopLevelRenamer | None = None,
        shell_editor: RepositoryShellBlockEditor | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not callable(provider):
            raise TypeError("provider must be callable")
        if not 1 <= int(max_operations) <= 64:
            raise ValueError("max_operations must be in [1, 64]")
        if int(max_source_bytes) <= 0 or int(max_total_output_bytes) <= 0:
            raise ValueError("byte limits must be positive")
        self.provider = provider
        self.max_operations = int(max_operations)
        self.max_source_bytes = int(max_source_bytes)
        self.max_total_output_bytes = int(max_total_output_bytes)
        self.patcher = patcher or RepositoryASTFunctionPatcher()
        self.renamer = renamer or RepositoryPythonTopLevelRenamer()
        self.shell_editor = shell_editor or RepositoryShellBlockEditor(
            max_body_chars=min(self.max_source_bytes, 1_000_000),
        )

    def __call__(
        self,
        plan: PatchPlan,
        context: RepositoryReadContext,
    ) -> tuple[FileEdit, ...]:
        raw_specs = tuple(self.provider(plan, context))
        return self.build_edits(plan, raw_specs)

    def build_edits(
        self,
        plan: PatchPlan,
        specs: Iterable[StructuredSpecInput],
    ) -> tuple[FileEdit, ...]:
        typed = tuple(_coerce_spec(item) for item in specs)
        if not typed:
            raise StructuredPatchError("provider returned no structured patch specs")
        if len(typed) > self.max_operations:
            raise StructuredPatchError("structured patch operation count exceeds bound")

        planned = {item.path: item for item in plan.files}
        grouped: dict[str, list[StructuredSpec]] = {}
        order: list[str] = []
        for spec in typed:
            path = _safe_relative_path(spec.path)
            if path not in grouped:
                grouped[path] = []
                order.append(path)
            grouped[path].append(spec)

        edits: list[FileEdit] = []
        total_output_bytes = 0
        for path in order:
            row = planned.get(path)
            if row is None:
                raise StructuredPatchError(f"structured patch path is not planned: {path}")
            rows = grouped[path]

            if row.operation == "create":
                if len(rows) != 1 or not isinstance(rows[0], CreateTextSpec):
                    raise StructuredPatchError(
                        f"planned create requires exactly one create_text op: {path}"
                    )
                content = rows[0].content
                size = len(content.encode("utf-8"))
                if size > self.max_source_bytes:
                    raise StructuredPatchError(f"create content exceeds byte bound: {path}")
                total_output_bytes += size
                edits.append(
                    FileEdit(
                        path=path,
                        operation="create",
                        before_sha256="",
                        content=content,
                    )
                )
                continue

            if row.operation == "delete":
                if len(rows) != 1 or not isinstance(rows[0], DeleteFileSpec):
                    raise StructuredPatchError(
                        f"planned delete requires exactly one delete_file op: {path}"
                    )
                edits.append(
                    FileEdit(
                        path=path,
                        operation="delete",
                        before_sha256=row.before_sha256,
                        content=None,
                    )
                )
                continue

            if row.operation != "modify":
                raise StructuredPatchError(
                    f"structured patch path is not a planned mutation: {path}"
                )
            if any(isinstance(item, (CreateTextSpec, DeleteFileSpec)) for item in rows):
                raise StructuredPatchError(
                    f"modify path cannot contain create/delete ops: {path}"
                )

            source = self._read_planned_source(path, row.before_sha256)
            current = source
            patched_symbols: set[str] = set()
            for spec in rows:
                if isinstance(spec, ExactReplaceSpec):
                    current = self._apply_exact_replace(current, path, spec)
                    continue
                if isinstance(spec, ShellBlockSpec):
                    try:
                        current = self.shell_editor.replace_for_path(
                            current,
                            path=path,
                            name=spec.name,
                            body=spec.body,
                        )
                    except ShellBlockEditError as exc:
                        raise StructuredPatchError(
                            f"shell_block rejected for {path}:{spec.name}:{exc}"
                        ) from exc
                    continue
                if isinstance(spec, PythonSymbolRenameSpec):
                    try:
                        current = self.renamer.rename(
                            current,
                            path=path,
                            old_name=spec.old_name,
                            new_name=spec.new_name,
                        )
                    except PythonSymbolRenameError as exc:
                        raise StructuredPatchError(
                            f"python_symbol_rename rejected for "
                            f"{path}:{spec.old_name}:{exc}"
                        ) from exc
                    continue
                if isinstance(spec, ASTPatchSpec):
                    if not path.endswith(".py"):
                        raise StructuredPatchError(
                            f"python_function_body requires a .py path: {path}"
                        )
                    symbol = str(spec.target_symbol or "").strip()
                    if not _SAFE_SYMBOL.fullmatch(symbol):
                        raise StructuredPatchError(
                            f"invalid target symbol for {path}: {symbol}"
                        )
                    if symbol in patched_symbols:
                        raise StructuredPatchError(
                            f"duplicate function-body target for {path}: {symbol}"
                        )
                    patched_symbols.add(symbol)
                    result = self.patcher.patch(
                        current,
                        path=path,
                        target_symbol=symbol,
                        replacement_body=spec.replacement_body,
                    )
                    if not result.ok:
                        raise StructuredPatchError(
                            f"AST patch rejected for {path}:{symbol}:"
                            + ",".join(result.errors)
                        )
                    current = result.content
                    continue
                raise StructuredPatchError(
                    f"unsupported modify operation for {path}: {type(spec).__name__}"
                )

            if current == source:
                raise StructuredPatchError(f"structured patch produced no change: {path}")
            size = len(current.encode("utf-8"))
            if size > self.max_source_bytes:
                raise StructuredPatchError(f"modified content exceeds byte bound: {path}")
            total_output_bytes += size
            edits.append(
                FileEdit(
                    path=path,
                    operation="modify",
                    before_sha256=row.before_sha256,
                    content=current,
                )
            )

        if total_output_bytes > self.max_total_output_bytes:
            raise StructuredPatchError("structured patch output exceeds total byte bound")
        return tuple(edits)

    def _read_planned_source(self, path: str, before_sha256: str) -> str:
        full = self.root / path
        if not full.is_file() or full.is_symlink():
            raise StructuredPatchError(f"structured patch source unavailable: {path}")
        raw = full.read_bytes()
        if len(raw) > self.max_source_bytes:
            raise StructuredPatchError(f"structured patch source exceeds byte bound: {path}")
        if sha256(raw).hexdigest() != before_sha256:
            raise StructuredPatchError(f"STALE_PLAN: source hash changed: {path}")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StructuredPatchError(
                f"structured patch source is not UTF-8: {path}"
            ) from exc

    @staticmethod
    def _apply_exact_replace(
        source: str,
        path: str,
        spec: ExactReplaceSpec,
    ) -> str:
        if not spec.old:
            raise StructuredPatchError(f"replace_exact old text is empty: {path}")
        if spec.old == spec.new:
            raise StructuredPatchError(f"replace_exact is a no-op: {path}")
        if not 1 <= int(spec.expected_count) <= 1000:
            raise StructuredPatchError(
                f"replace_exact expected_count must be in [1, 1000]: {path}"
            )
        actual = source.count(spec.old)
        if actual != int(spec.expected_count):
            raise StructuredPatchError(
                f"replace_exact count mismatch for {path}: "
                f"expected={spec.expected_count} actual={actual}"
            )
        return source.replace(spec.old, spec.new, int(spec.expected_count))


class StructuredRepairProvider:
    """Adapt structured repair specs to the existing bounded repair loop."""

    def __init__(
        self,
        proposal_provider: RepositoryStructuredProposalProvider,
        plan: PatchPlan,
        provider: StructuredRepairSpecProvider,
    ) -> None:
        if not callable(provider):
            raise TypeError("provider must be callable")
        self.proposal_provider = proposal_provider
        self.plan = plan
        self.provider = provider

    def __call__(
        self,
        current: tuple[FileEdit, ...],
        attempt: CandidateAttempt,
    ) -> tuple[FileEdit, ...] | None:
        specs = self.provider(current, attempt)
        if specs is None:
            return None
        return self.proposal_provider.build_edits(self.plan, tuple(specs))


def _coerce_spec(spec: StructuredSpecInput) -> StructuredSpec:
    if isinstance(
        spec,
        (
            ASTPatchSpec,
            PythonSymbolRenameSpec,
            ShellBlockSpec,
            ExactReplaceSpec,
            CreateTextSpec,
            DeleteFileSpec,
        ),
    ):
        return spec
    if isinstance(spec, Mapping):
        return structured_spec_from_mapping(spec)
    raise TypeError(f"unsupported structured spec type: {type(spec).__name__}")


def _safe_relative_path(raw: str) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or "\x00" in value
        or any(part in {"", ".", "..", ".git"} for part in posix.parts)
        or any(not _SAFE_SEGMENT.fullmatch(part) for part in posix.parts)
    ):
        raise StructuredPatchError("path must be a safe relative repository path")
    return posix.as_posix()
