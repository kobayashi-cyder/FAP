from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import ast
import re
from typing import Callable, Iterable

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan
from fap_repository_reader import RepositoryReadContext
from fap_repository_verifier import CandidateAttempt


class ASTPatchError(RuntimeError):
    """Raised when a bounded function-body patch cannot be formed safely."""


@dataclass(frozen=True)
class ASTPatchSpec:
    path: str
    target_symbol: str
    replacement_body: str


@dataclass(frozen=True)
class ASTPatchResult:
    version: str
    ok: bool
    path: str
    target_symbol: str
    before_sha256: str
    after_sha256: str
    content: str
    changed_lines: tuple[int, int] | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self, *, include_content: bool = False) -> dict:
        out = asdict(self)
        if not include_content:
            out.pop("content", None)
        return out

    def to_file_edit(self) -> FileEdit:
        if not self.ok:
            raise ASTPatchError("cannot convert rejected AST patch to FileEdit")
        return FileEdit(
            path=self.path,
            operation="modify",
            before_sha256=self.before_sha256,
            content=self.content,
        )


class RepositoryASTFunctionPatcher:
    """Pure AST-located replacement of one existing Python function body.

    The patcher never writes files, imports target code, invokes subprocesses or
    runs git. It locates one function by AST path, replaces only that function's
    executable body while preserving any docstring, then verifies that the
    function signature/decorators and all source bytes outside the replacement
    region remain unchanged.
    """

    VERSION = "fap.repository.ast_patch.v1"
    _SAFE_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.py")
    _ALLOWED_IMPORT_ROOTS = frozenset(
        {"collections", "functools", "itertools", "json", "math", "re", "statistics"}
    )
    _FORBIDDEN_CALLS = frozenset(
        {"eval", "exec", "compile", "__import__", "open", "input"}
    )

    def patch(
        self,
        source: str,
        *,
        path: str,
        target_symbol: str,
        replacement_body: str,
    ) -> ASTPatchResult:
        if not isinstance(source, str):
            raise TypeError("source must be text")
        path = self._safe_path(path)
        symbol = str(target_symbol or "").strip()
        body = str(replacement_body or "").strip("\r\n")
        if not symbol:
            raise ValueError("target_symbol is required")
        if not body.strip():
            raise ValueError("replacement_body is required")

        before_sha = sha256(source.encode("utf-8")).hexdigest()
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            return self._reject(
                path, symbol, source, before_sha, (f"source_syntax:{exc.lineno}",)
            )

        target = self._find_function(tree, symbol)
        if target is None:
            return self._reject(
                path, symbol, source, before_sha, ("target_symbol_not_found",)
            )
        if not target.body:
            return self._reject(
                path, symbol, source, before_sha, ("target_function_has_no_body",)
            )

        keep_docstring = self._has_docstring(target)
        replace_index = 1 if keep_docstring else 0
        if replace_index >= len(target.body):
            return self._reject(
                path, symbol, source, before_sha, ("docstring_only_function_not_patchable",)
            )

        first = target.body[replace_index]
        last = target.body[-1]
        if first.lineno is None or last.end_lineno is None:
            return self._reject(
                path, symbol, source, before_sha, ("source_location_unavailable",)
            )

        body_errors = self._validate_replacement_body(body)
        if body_errors:
            return self._reject(path, symbol, source, before_sha, body_errors)

        lines = source.splitlines(keepends=True)
        if not (1 <= first.lineno <= len(lines)):
            return self._reject(
                path, symbol, source, before_sha, ("source_location_out_of_bounds",)
            )

        indent_match = re.match(r"[ \t]*", lines[first.lineno - 1])
        indent = indent_match.group(0) if indent_match else (" " * (target.col_offset + 4))
        newline = "\r\n" if "\r\n" in source else "\n"
        replacement = self._indent_body(body, indent, newline)
        prefix = "".join(lines[: first.lineno - 1])
        suffix = "".join(lines[last.end_lineno :])
        patched = prefix + replacement + suffix

        checks = [
            "source_ast_parse",
            "target_symbol_resolved",
            "replacement_body_ast_policy",
            "bounded_function_body_replacement",
        ]
        errors: list[str] = []
        try:
            patched_tree = ast.parse(patched, filename=path)
            compile(patched_tree, path, "exec")
            checks.append("patched_compile")
        except SyntaxError as exc:
            return self._reject(
                path,
                symbol,
                source,
                before_sha,
                (f"patched_syntax:{exc.lineno}",),
            )

        patched_target = self._find_function(patched_tree, symbol)
        if patched_target is None:
            errors.append("patched_symbol_missing")
        else:
            if ast.dump(target.args, include_attributes=False) != ast.dump(
                patched_target.args, include_attributes=False
            ):
                errors.append("signature_changed")
            else:
                checks.append("signature_ast_equal")

            original_decorators = tuple(
                ast.dump(item, include_attributes=False)
                for item in target.decorator_list
            )
            patched_decorators = tuple(
                ast.dump(item, include_attributes=False)
                for item in patched_target.decorator_list
            )
            if original_decorators != patched_decorators:
                errors.append("decorators_changed")
            else:
                checks.append("decorators_ast_equal")

            if self._docstring_value(target) != self._docstring_value(patched_target):
                errors.append("docstring_changed")
            else:
                checks.append("docstring_preserved")

        if patched[: len(prefix)] != prefix or patched[len(patched) - len(suffix) :] != suffix:
            errors.append("outside_region_changed")
        else:
            checks.append("outside_region_byte_stable")

        return ASTPatchResult(
            version=self.VERSION,
            ok=not errors,
            path=path,
            target_symbol=symbol,
            before_sha256=before_sha,
            after_sha256=sha256(patched.encode("utf-8")).hexdigest(),
            content=patched,
            changed_lines=(first.lineno, last.end_lineno),
            checks=tuple(checks),
            errors=tuple(errors),
        )

    @classmethod
    def _safe_path(cls, raw: str) -> str:
        value = str(raw or "").strip().replace("\\", "/")
        posix = PurePosixPath(value)
        if (
            not value
            or not cls._SAFE_PATH.fullmatch(value)
            or posix.is_absolute()
            or any(part in {"", ".", "..", ".git"} for part in posix.parts)
            or "\x00" in value
        ):
            raise ValueError("path must be a safe relative .py path")
        return posix.as_posix()

    @classmethod
    def _find_function(
        cls,
        tree: ast.AST,
        target_symbol: str,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        parts = tuple(part for part in target_symbol.split(".") if part)
        if not parts:
            return None

        body = getattr(tree, "body", ())
        current: ast.AST | None = None
        for index, part in enumerate(parts):
            matches = [
                item
                for item in body
                if isinstance(
                    item,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                )
                and item.name == part
            ]
            if len(matches) != 1:
                return None
            current = matches[0]
            if index < len(parts) - 1:
                if not isinstance(current, ast.ClassDef):
                    return None
                body = current.body
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        return None

    @staticmethod
    def _has_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        if not node.body:
            return False
        first = node.body[0]
        return (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )

    @classmethod
    def _docstring_value(
        cls,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str | None:
        if not cls._has_docstring(node):
            return None
        value = node.body[0]
        assert isinstance(value, ast.Expr)
        assert isinstance(value.value, ast.Constant)
        return str(value.value.value)

    @classmethod
    def _validate_replacement_body(cls, body: str) -> tuple[str, ...]:
        wrapper = "def __fap_ast_patch_probe__():\n"
        for line in body.splitlines():
            wrapper += "    " + line + "\n"
        try:
            tree = ast.parse(wrapper, filename="<fap-ast-patch>")
            compile(tree, "<fap-ast-patch>", "exec")
        except SyntaxError as exc:
            return (f"replacement_body_syntax:{exc.lineno}",)

        errors: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root not in cls._ALLOWED_IMPORT_ROOTS:
                        errors.append(f"replacement_forbidden_import:{root}")
            elif isinstance(node, ast.ImportFrom):
                root = str(node.module or "").split(".", 1)[0]
                if root not in cls._ALLOWED_IMPORT_ROOTS:
                    errors.append(f"replacement_forbidden_import:{root}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in cls._FORBIDDEN_CALLS
            ):
                errors.append(f"replacement_forbidden_call:{node.func.id}")

        return tuple(dict.fromkeys(errors))

    @staticmethod
    def _indent_body(body: str, indent: str, newline: str) -> str:
        rows = body.splitlines()
        return "".join(f"{indent}{row}{newline}" for row in rows)

    def _reject(
        self,
        path: str,
        target_symbol: str,
        source: str,
        before_sha: str,
        errors: tuple[str, ...],
    ) -> ASTPatchResult:
        return ASTPatchResult(
            version=self.VERSION,
            ok=False,
            path=path,
            target_symbol=target_symbol,
            before_sha256=before_sha,
            after_sha256=before_sha,
            content=source,
            changed_lines=None,
            checks=(),
            errors=errors,
        )


PatchSpecProvider = Callable[
    [PatchPlan, RepositoryReadContext],
    Iterable[ASTPatchSpec],
]
RepairSpecProvider = Callable[
    [tuple[FileEdit, ...], CandidateAttempt],
    Iterable[ASTPatchSpec] | None,
]


class ASTLimitedProposalProvider:
    """Adapt ASTPatchSpec objects to FAP's existing repository proposer boundary."""

    def __init__(
        self,
        root: str | Path,
        provider: PatchSpecProvider,
        *,
        max_patches: int = 4,
        max_source_bytes: int = 500_000,
        patcher: RepositoryASTFunctionPatcher | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not callable(provider):
            raise TypeError("provider must be callable")
        if not 1 <= int(max_patches) <= 8:
            raise ValueError("max_patches must be in [1, 8]")
        self.provider = provider
        self.max_patches = int(max_patches)
        self.max_source_bytes = int(max_source_bytes)
        self.patcher = patcher or RepositoryASTFunctionPatcher()

    def __call__(
        self,
        plan: PatchPlan,
        context: RepositoryReadContext,
    ) -> tuple[FileEdit, ...]:
        specs = tuple(self.provider(plan, context))
        return self._build_edits(plan, specs)

    def _build_edits(
        self,
        plan: PatchPlan,
        specs: tuple[ASTPatchSpec, ...],
    ) -> tuple[FileEdit, ...]:
        if not specs:
            raise ASTPatchError("provider returned no AST patch specs")
        if len(specs) > self.max_patches:
            raise ASTPatchError("AST patch count exceeds bound")

        planned = {item.path: item for item in plan.files}
        edits: list[FileEdit] = []
        seen: set[str] = set()
        for spec in specs:
            path = self.patcher._safe_path(spec.path)
            if path in seen:
                raise ASTPatchError(f"duplicate AST patch path: {path}")
            seen.add(path)

            row = planned.get(path)
            if row is None or row.operation != "modify":
                raise ASTPatchError(f"AST patch path is not a planned modify: {path}")
            full = self.root / path
            if not full.is_file() or full.is_symlink():
                raise ASTPatchError(f"AST patch source unavailable: {path}")
            raw = full.read_bytes()
            if len(raw) > self.max_source_bytes:
                raise ASTPatchError(f"AST patch source exceeds byte bound: {path}")
            try:
                source = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ASTPatchError(f"AST patch source is not UTF-8: {path}") from exc

            actual = sha256(raw).hexdigest()
            if actual != row.before_sha256:
                raise ASTPatchError(f"STALE_PLAN: source hash changed: {path}")

            result = self.patcher.patch(
                source,
                path=path,
                target_symbol=spec.target_symbol,
                replacement_body=spec.replacement_body,
            )
            if not result.ok:
                raise ASTPatchError(
                    f"AST patch rejected for {path}:{spec.target_symbol}:"
                    + ",".join(result.errors)
                )
            edits.append(result.to_file_edit())
        return tuple(edits)


class ASTLimitedRepairProvider:
    """Bounded repair adapter that re-derives each repair from original sources."""

    def __init__(
        self,
        proposal_provider: ASTLimitedProposalProvider,
        plan: PatchPlan,
        provider: RepairSpecProvider,
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
        return self.proposal_provider._build_edits(self.plan, tuple(specs))
