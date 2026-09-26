from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import ast
import re

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


class PythonInsertError(RuntimeError):
    pass


@dataclass(frozen=True)
class PythonFunctionInsertSpec:
    path: str
    function_source: str


@dataclass(frozen=True)
class PythonFunctionInsertResult:
    ok: bool
    path: str
    function_name: str
    before_sha256: str
    after_sha256: str
    content: str
    errors: tuple[str, ...]

    def to_dict(self, *, include_content: bool = False) -> dict:
        out = asdict(self)
        if not include_content:
            out.pop("content", None)
        return out

    def to_file_edit(self) -> FileEdit:
        if not self.ok:
            raise PythonInsertError("cannot convert rejected insert to FileEdit")
        return FileEdit(
            path=self.path,
            operation="modify",
            before_sha256=self.before_sha256,
            content=self.content,
        )


class RepositoryPythonFunctionInserter:
    """Append one validated top-level Python function without rewriting existing code."""

    VERSION = "fap.repository.python_insert.v1"
    _SAFE_PATH = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.py$")
    _FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__", "open", "input"})
    _FORBIDDEN_IMPORTS = frozenset({"subprocess", "socket", "ctypes", "multiprocessing"})

    def __init__(self, *, max_function_chars: int = 20_000) -> None:
        if not 64 <= int(max_function_chars) <= 200_000:
            raise ValueError("max_function_chars must be in [64, 200000]")
        self.max_function_chars = int(max_function_chars)

    def insert(
        self,
        source: str,
        *,
        path: str,
        function_source: str,
    ) -> PythonFunctionInsertResult:
        path = str(path or "").strip().replace("\\", "/")
        if not self._SAFE_PATH.fullmatch(path):
            raise ValueError("path must be a safe relative .py path")
        before_sha = sha256(source.encode("utf-8")).hexdigest()

        try:
            original_tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            return self._reject(
                path,
                "",
                source,
                before_sha,
                (f"source_syntax:{exc.lineno}",),
            )

        snippet = str(function_source or "").strip()
        if not snippet:
            raise ValueError("function_source is required")
        if len(snippet) > self.max_function_chars:
            raise ValueError("function_source exceeds character limit")
        try:
            snippet_tree = ast.parse(snippet + "\n", filename="<fap-python-insert>")
        except SyntaxError as exc:
            return self._reject(
                path,
                "",
                source,
                before_sha,
                (f"function_syntax:{exc.lineno}",),
            )

        if len(snippet_tree.body) != 1 or not isinstance(
            snippet_tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            return self._reject(
                path,
                "",
                source,
                before_sha,
                ("exactly_one_function_required",),
            )
        function = snippet_tree.body[0]
        name = function.name

        existing = {
            node.name
            for node in original_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        if name in existing:
            return self._reject(
                path,
                name,
                source,
                before_sha,
                ("symbol_already_exists",),
            )

        policy_errors = self._policy_errors(function)
        if policy_errors:
            return self._reject(path, name, source, before_sha, policy_errors)

        suffix = "" if source.endswith("\n") else "\n"
        separator = "\n" if source.strip() else ""
        content = source + suffix + separator + snippet.rstrip() + "\n"
        try:
            patched = ast.parse(content, filename=path)
            compile(patched, path, "exec")
        except SyntaxError as exc:
            return self._reject(
                path,
                name,
                source,
                before_sha,
                (f"patched_syntax:{exc.lineno}",),
            )

        old_dump = tuple(
            ast.dump(node, include_attributes=False)
            for node in original_tree.body
        )
        new_prefix = tuple(
            ast.dump(node, include_attributes=False)
            for node in patched.body[: len(original_tree.body)]
        )
        if old_dump != new_prefix:
            return self._reject(
                path,
                name,
                source,
                before_sha,
                ("existing_module_ast_changed",),
            )

        return PythonFunctionInsertResult(
            ok=True,
            path=path,
            function_name=name,
            before_sha256=before_sha,
            after_sha256=sha256(content.encode("utf-8")).hexdigest(),
            content=content,
            errors=(),
        )

    def from_plan(
        self,
        root: str | Path,
        plan: PatchPlan,
        spec: PythonFunctionInsertSpec,
    ) -> FileEdit:
        rows = {item.path: item for item in plan.files}
        planned = rows.get(spec.path)
        if planned is None or planned.operation != "modify":
            raise PythonInsertError("insert path is not a planned modify")
        full = Path(root).expanduser().resolve() / spec.path
        if not full.is_file() or full.is_symlink():
            raise PythonInsertError("insert source unavailable")
        raw = full.read_bytes()
        if sha256(raw).hexdigest() != planned.before_sha256:
            raise PythonInsertError("STALE_PLAN: source hash changed")
        source = raw.decode("utf-8")
        result = self.insert(
            source,
            path=spec.path,
            function_source=spec.function_source,
        )
        if not result.ok:
            raise PythonInsertError(",".join(result.errors))
        return result.to_file_edit()

    @classmethod
    def _policy_errors(
        cls,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> tuple[str, ...]:
        errors: list[str] = []

        if function.decorator_list:
            errors.append("decorators_not_allowed")

        definition_time_nodes: list[ast.AST] = []
        definition_time_nodes.extend(function.args.defaults)
        definition_time_nodes.extend(
            item for item in function.args.kw_defaults if item is not None
        )
        definition_time_nodes.extend(
            arg.annotation
            for arg in (
                *function.args.posonlyargs,
                *function.args.args,
                *function.args.kwonlyargs,
            )
            if arg.annotation is not None
        )
        if function.args.vararg and function.args.vararg.annotation is not None:
            definition_time_nodes.append(function.args.vararg.annotation)
        if function.args.kwarg and function.args.kwarg.annotation is not None:
            definition_time_nodes.append(function.args.kwarg.annotation)
        if function.returns is not None:
            definition_time_nodes.append(function.returns)

        if any(
            isinstance(node, ast.Call)
            for root in definition_time_nodes
            for node in ast.walk(root)
        ):
            errors.append("definition_time_call_not_allowed")

        for node in ast.walk(function):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in cls._FORBIDDEN_IMPORTS:
                        errors.append(f"forbidden_import:{root}")
            elif isinstance(node, ast.ImportFrom):
                root = str(node.module or "").split(".", 1)[0]
                if root in cls._FORBIDDEN_IMPORTS:
                    errors.append(f"forbidden_import:{root}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in cls._FORBIDDEN_CALLS
            ):
                errors.append(f"forbidden_call:{node.func.id}")
        return tuple(dict.fromkeys(errors))

    @staticmethod
    def _reject(
        path: str,
        name: str,
        source: str,
        before_sha: str,
        errors: tuple[str, ...],
    ) -> PythonFunctionInsertResult:
        return PythonFunctionInsertResult(
            ok=False,
            path=path,
            function_name=name,
            before_sha256=before_sha,
            after_sha256=before_sha,
            content=source,
            errors=errors,
        )
