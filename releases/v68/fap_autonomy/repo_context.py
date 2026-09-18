from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple


class RepositoryContextError(ValueError):
    pass


@dataclass(frozen=True)
class RepoFile:
    path: str
    sha256: str
    bytes: int
    symbols: Tuple[str, ...]


@dataclass(frozen=True)
class RepositoryContext:
    root: str
    digest: str
    files: Tuple[RepoFile, ...]
    symbol_index: Dict[str, Tuple[str, ...]]

    def to_dict(self):
        return {
            'root': self.root,
            'digest': self.digest,
            'files': [asdict(x) for x in self.files],
            'symbol_index': {k: list(v) for k, v in sorted(self.symbol_index.items())},
        }


class RepositoryContextBuilder:
    """Read-only Python repository index with strict path/symlink/size bounds."""

    def __init__(self, *, max_file_bytes: int = 256_000, max_total_bytes: int = 2_000_000):
        self.max_file_bytes = int(max_file_bytes)
        self.max_total_bytes = int(max_total_bytes)
        if self.max_file_bytes < 1 or self.max_total_bytes < self.max_file_bytes:
            raise ValueError('invalid context budget')

    @staticmethod
    def _symbols(source: str, filename: str) -> Tuple[str, ...]:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError:
            return ()
        out = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and not t.id.startswith('_'):
                        out.append(t.id)
        return tuple(sorted(set(out)))

    def build(self, root: str) -> RepositoryContext:
        base = Path(root).resolve()
        if not base.is_dir():
            raise RepositoryContextError('repository root missing')
        if base.is_symlink():
            raise RepositoryContextError('repository root may not be a symlink')
        for p in base.rglob('*'):
            if p.is_symlink():
                raise RepositoryContextError(f'symlink not allowed: {p.relative_to(base)}')

        total = 0
        files: List[RepoFile] = []
        symbol_map: Dict[str, List[str]] = {}
        h = hashlib.sha256()
        for p in sorted(base.rglob('*.py')):
            rel = p.relative_to(base)
            if any(part in {'.git', '__pycache__', '.venv', 'venv'} for part in rel.parts):
                continue
            size = p.stat().st_size
            if size > self.max_file_bytes:
                continue
            total += size
            if total > self.max_total_bytes:
                raise RepositoryContextError('repository context budget exceeded')
            raw = p.read_bytes()
            try:
                source = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
            digest = hashlib.sha256(raw).hexdigest()
            syms = self._symbols(source, str(rel))
            rels = rel.as_posix()
            files.append(RepoFile(rels, digest, size, syms))
            h.update(rels.encode('utf-8')); h.update(b'\0'); h.update(raw); h.update(b'\0')
            for sym in syms:
                symbol_map.setdefault(sym, []).append(rels)
        index = {k: tuple(v) for k, v in sorted(symbol_map.items())}
        return RepositoryContext(str(base), h.hexdigest(), tuple(files), index)

    @staticmethod
    def relevant_files(context: RepositoryContext, text: str, *, limit: int = 8) -> List[str]:
        terms = {x.strip(".,:;()[]{}'\"` ") for x in str(text).replace('\n', ' ').split()}
        terms = {x for x in terms if x}
        scored = []
        for f in context.files:
            score = sum(3 for s in f.symbols if s in terms)
            score += sum(1 for t in terms if t and t.lower() in f.path.lower())
            scored.append((score, f.path))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [p for score, p in scored[:max(1, int(limit))] if score > 0] or [f.path for f in context.files[:max(1, int(limit))]]
