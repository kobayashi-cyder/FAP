from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import argparse
import ast
import json
import os
from typing import Iterable


DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".venv", "venv", "env", "node_modules",
    "dist", "build", ".idea", ".vscode", "runtime", "artifacts",
}

TEXT_EXTENSIONS = {
    ".py", ".md", ".json", ".jsonl", ".toml", ".yaml", ".yml",
    ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".cmd",
}


@dataclass(frozen=True)
class SymbolRecord:
    name: str
    kind: str
    path: str
    line: int
    end_line: int | None
    signature: str
    parent: str | None = None


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str
    language: str
    parse_status: str
    imports: tuple[str, ...] = ()
    symbols: tuple[SymbolRecord, ...] = ()


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class RepositoryIndex:
    root: str
    files: tuple[FileRecord, ...]
    dependencies: tuple[DependencyEdge, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryIndexer:
    """Read-only repository mapper for FAP.

    Safety properties:
    - never imports or executes project code;
    - reads only files under the configured root;
    - ignores common generated/vendor/runtime directories;
    - applies a per-file byte limit before parsing;
    - records parse failures instead of guessing.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS,
        max_file_bytes: int = 1_000_000,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.root}")
        self.ignore_dirs = frozenset(str(x) for x in ignore_dirs)
        self.max_file_bytes = int(max_file_bytes)
        if self.max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")

    def build(self) -> RepositoryIndex:
        files: list[FileRecord] = []
        errors: list[str] = []
        for path in self._iter_candidate_files():
            try:
                files.append(self._scan_file(path))
            except Exception as exc:
                rel = self._relative(path)
                errors.append(f"{rel}: {type(exc).__name__}: {exc}")

        files.sort(key=lambda r: r.path)
        deps = self._resolve_dependencies(files)
        return RepositoryIndex(
            root=str(self.root),
            files=tuple(files),
            dependencies=tuple(deps),
            errors=tuple(errors),
        )

    def _iter_candidate_files(self) -> Iterable[Path]:
        for current, dirs, names in os.walk(self.root, followlinks=False):
            current_path = Path(current).resolve()
            # Prevent accidental traversal through paths that resolved outside root.
            if not self._inside_root(current_path):
                dirs[:] = []
                continue
            dirs[:] = sorted(
                d for d in dirs
                if d not in self.ignore_dirs and not d.startswith(".git")
            )
            for name in sorted(names):
                path = current_path / name
                if path.is_symlink():
                    continue
                if path.suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                if self._inside_root(path.resolve()):
                    yield path

    def _scan_file(self, path: Path) -> FileRecord:
        rel = self._relative(path)
        size = path.stat().st_size
        digest = _sha256_file(path)
        lang = _language_for(path)
        if size > self.max_file_bytes:
            return FileRecord(
                path=rel,
                size=size,
                sha256=digest,
                language=lang,
                parse_status="skipped:size_limit",
            )

        raw = path.read_bytes()
        if path.suffix.lower() != ".py":
            return FileRecord(
                path=rel,
                size=size,
                sha256=digest,
                language=lang,
                parse_status="text",
            )

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8-sig")
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            return FileRecord(
                path=rel,
                size=size,
                sha256=digest,
                language=lang,
                parse_status=f"syntax_error:{exc.lineno or 0}",
            )

        symbols = tuple(_extract_python_symbols(tree, rel))
        imports = tuple(sorted(set(_extract_python_imports(tree, rel))))
        return FileRecord(
            path=rel,
            size=size,
            sha256=digest,
            language=lang,
            parse_status="parsed",
            imports=imports,
            symbols=symbols,
        )

    def _resolve_dependencies(self, files: list[FileRecord]) -> list[DependencyEdge]:
        module_to_path: dict[str, str] = {}
        for rec in files:
            if not rec.path.endswith(".py"):
                continue
            module = rec.path[:-3].replace("/", ".").replace("\\", ".")
            if module.endswith(".__init__"):
                module = module[:-9]
            module_to_path[module] = rec.path

        edges: set[tuple[str, str, str]] = set()
        for rec in files:
            if not rec.imports:
                continue
            for imported in rec.imports:
                candidates = [imported]
                parts = imported.split(".")
                candidates.extend(".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1))
                target = next((module_to_path[c] for c in candidates if c in module_to_path), None)
                if target and target != rec.path:
                    edges.add((rec.path, target, "python_import"))
        return [DependencyEdge(*edge) for edge in sorted(edges)]

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def _inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.root)
            return True
        except ValueError:
            return False


def _language_for(path: Path) -> str:
    return {
        ".py": "python", ".md": "markdown", ".json": "json", ".jsonl": "jsonl",
        ".toml": "toml", ".yaml": "yaml", ".yml": "yaml", ".html": "html",
        ".css": "css", ".js": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".jsx": "javascript", ".sh": "shell",
        ".ps1": "powershell", ".cmd": "cmd",
    }.get(path.suffix.lower(), "text")


def _extract_python_imports(tree: ast.AST, path: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from(path, node.level, node.module)
            if base:
                found.append(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                if base:
                    found.append(f"{base}.{alias.name}")
                elif node.level == 0 and not node.module:
                    found.append(alias.name)
    return found


def _resolve_import_from(path: str, level: int, module: str | None) -> str:
    if level == 0:
        return str(module or "")
    package = path[:-3].replace("/", ".").replace("\\", ".").split(".")[:-1]
    ascend = level - 1
    if ascend > len(package):
        return ""
    base = package[: len(package) - ascend] if ascend else package
    if module:
        base.extend(str(module).split("."))
    return ".".join(x for x in base if x)


def _sha256_file(path: Path, chunk_size: int = 128 * 1024) -> str:
    h = sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _extract_python_symbols(tree: ast.AST, path: str) -> list[SymbolRecord]:
    out: list[SymbolRecord] = []

    def signature(node: ast.AST) -> str:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = []
            pos = list(node.args.posonlyargs) + list(node.args.args)
            defaults = [None] * (len(pos) - len(node.args.defaults)) + list(node.args.defaults)
            for arg, default in zip(pos, defaults):
                piece = arg.arg
                if arg.annotation is not None:
                    piece += ": " + _safe_unparse(arg.annotation)
                if default is not None:
                    piece += "=" + _safe_unparse(default)
                args.append(piece)
            if node.args.vararg:
                args.append("*" + node.args.vararg.arg)
            elif node.args.kwonlyargs:
                args.append("*")
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                piece = arg.arg
                if arg.annotation is not None:
                    piece += ": " + _safe_unparse(arg.annotation)
                if default is not None:
                    piece += "=" + _safe_unparse(default)
                args.append(piece)
            if node.args.kwarg:
                args.append("**" + node.args.kwarg.arg)
            ret = ""
            if node.returns is not None:
                ret = " -> " + _safe_unparse(node.returns)
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            return f"{prefix} {node.name}({', '.join(args)}){ret}"
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(_safe_unparse(x) for x in node.bases)
            return f"class {node.name}" + (f"({bases})" if bases else "")
        return getattr(node, "name", type(node).__name__)

    def visit_body(body: list[ast.stmt], parent: str | None = None) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                out.append(SymbolRecord(
                    name=node.name, kind="class", path=path, line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    signature=signature(node), parent=parent,
                ))
                visit_body(node.body, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if parent else ("async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
                out.append(SymbolRecord(
                    name=node.name, kind=kind, path=path, line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    signature=signature(node), parent=parent,
                ))
                # Nested functions are relevant, but keep the parent path explicit.
                visit_body(node.body, f"{parent + '.' if parent else ''}{node.name}")
    visit_body(getattr(tree, "body", []))
    return out


def _safe_unparse(node: ast.AST) -> str:
    try:
        text = ast.unparse(node)
    except Exception:
        return "?"
    return " ".join(text.split())[:200]


def render_repository_map(index: RepositoryIndex, *, max_symbols_per_file: int = 12) -> str:
    lines: list[str] = []
    lines.append(f"# Repository Map")
    lines.append(f"root: {index.root}")
    lines.append(f"files: {len(index.files)}")
    lines.append(f"dependencies: {len(index.dependencies)}")
    if index.errors:
        lines.append(f"errors: {len(index.errors)}")
    lines.append("")

    for rec in index.files:
        lines.append(f"## {rec.path} [{rec.language}; {rec.parse_status}; {rec.size} bytes]")
        if rec.imports:
            lines.append("imports: " + ", ".join(rec.imports[:20]))
        for sym in rec.symbols[:max_symbols_per_file]:
            parent = f" parent={sym.parent}" if sym.parent else ""
            lines.append(f"- L{sym.line} {sym.kind}{parent}: {sym.signature}")
        if len(rec.symbols) > max_symbols_per_file:
            lines.append(f"- ... {len(rec.symbols) - max_symbols_per_file} more symbols")
        lines.append("")

    if index.dependencies:
        lines.append("# Internal Dependency Edges")
        for edge in index.dependencies:
            lines.append(f"- {edge.source} -> {edge.target} ({edge.kind})")
    if index.errors:
        lines.append("")
        lines.append("# Scan Errors")
        lines.extend(f"- {e}" for e in index.errors)
    return "\n".join(lines).rstrip() + "\n"


def build_repository_context(root: str | Path, *, max_symbols_per_file: int = 12) -> dict:
    """Adapter-friendly entry point for FAP's future Repository Coding Agent."""
    index = RepositoryIndexer(root).build()
    return {
        "index": index.to_dict(),
        "map": render_repository_map(index, max_symbols_per_file=max_symbols_per_file),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FAP read-only repository map + symbol index")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    parser.add_argument("--max-file-bytes", type=int, default=1_000_000)
    parser.add_argument("--max-symbols-per-file", type=int, default=12)
    args = parser.parse_args(argv)

    index = RepositoryIndexer(args.root, max_file_bytes=args.max_file_bytes).build()
    if args.json:
        print(json.dumps(index.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_repository_map(index, max_symbols_per_file=args.max_symbols_per_file), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
