from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path
import ast
import re
import tokenize

from fap_repository_executor import FileEdit
from fap_repository_planner import PatchPlan


class PythonSymbolRenameError(RuntimeError):
    pass


@dataclass(frozen=True)
class PythonSymbolRenameSpec:
    path: str
    old_name: str
    new_name: str


class RepositoryPythonTopLevelRenamer:
    """Conservatively rename one top-level Python function/class and references."""

    VERSION = "fap.repository.python_symbol_rename.v1"
    _NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def rename(
        self,
        source: str,
        *,
        path: str,
        old_name: str,
        new_name: str,
    ) -> str:
        if not path.endswith(".py"):
            raise PythonSymbolRenameError("path must be .py")
        if not self._NAME.fullmatch(old_name) or not self._NAME.fullmatch(new_name):
            raise PythonSymbolRenameError("symbol names must be Python identifiers")
        if old_name == new_name:
            raise PythonSymbolRenameError("old_name and new_name must differ")

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            raise PythonSymbolRenameError(
                f"source_syntax:{exc.lineno}"
            ) from exc

        top = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        matches = [node for node in top if node.name == old_name]
        if len(matches) != 1:
            raise PythonSymbolRenameError(
                f"expected exactly one top-level symbol {old_name!r}"
            )
        if any(node.name == new_name for node in top):
            raise PythonSymbolRenameError("new_name already exists at top level")

        self._reject_ambiguous_bindings(tree, old_name)

        tokens = []
        replaced = 0
        stream = StringIO(source).readline
        for token in tokenize.generate_tokens(stream):
            if token.type == tokenize.NAME and token.string == old_name:
                token = tokenize.TokenInfo(
                    token.type,
                    new_name,
                    token.start,
                    token.end,
                    token.line,
                )
                replaced += 1
            tokens.append(token)
        if replaced < 1:
            raise PythonSymbolRenameError("symbol token not found")

        patched = tokenize.untokenize(tokens)
        try:
            patched_tree = ast.parse(patched, filename=path)
            compile(patched_tree, path, "exec")
        except SyntaxError as exc:
            raise PythonSymbolRenameError(
                f"patched_syntax:{exc.lineno}"
            ) from exc

        patched_top = [
            node for node in patched_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        if any(node.name == old_name for node in patched_top):
            raise PythonSymbolRenameError("old top-level symbol remains after rename")
        if sum(node.name == new_name for node in patched_top) != 1:
            raise PythonSymbolRenameError("new top-level symbol is ambiguous after rename")
        return patched

    def build_edit(
        self,
        root: str | Path,
        plan: PatchPlan,
        spec: PythonSymbolRenameSpec,
    ) -> FileEdit:
        planned = next((x for x in plan.files if x.path == spec.path), None)
        if planned is None or planned.operation != "modify":
            raise PythonSymbolRenameError("rename path is not a planned modify")
        full = Path(root).expanduser().resolve() / spec.path
        if not full.is_file() or full.is_symlink():
            raise PythonSymbolRenameError("rename source unavailable")
        raw = full.read_bytes()
        if sha256(raw).hexdigest() != planned.before_sha256:
            raise PythonSymbolRenameError("STALE_PLAN: source hash changed")
        source = raw.decode("utf-8")
        content = self.rename(
            source,
            path=spec.path,
            old_name=spec.old_name,
            new_name=spec.new_name,
        )
        return FileEdit(
            path=spec.path,
            operation="modify",
            before_sha256=planned.before_sha256,
            content=content,
        )

    @staticmethod
    def _reject_ambiguous_bindings(tree: ast.AST, old_name: str) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.arg) and node.arg == old_name:
                raise PythonSymbolRenameError("ambiguous_argument_binding")
            if (
                isinstance(node, ast.Name)
                and node.id == old_name
                and isinstance(node.ctx, (ast.Store, ast.Del))
            ):
                raise PythonSymbolRenameError("ambiguous_name_binding")
            if isinstance(node, ast.Attribute) and node.attr == old_name:
                raise PythonSymbolRenameError("ambiguous_attribute_reference")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] == old_name or alias.asname == old_name:
                        raise PythonSymbolRenameError("ambiguous_import_binding")
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == old_name or alias.asname == old_name:
                        raise PythonSymbolRenameError("ambiguous_import_binding")
