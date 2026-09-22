from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re

from fap_repository_index import FileRecord, RepositoryIndex, RepositoryIndexer


QUERY_ALIASES = {
    "リポジトリ": ("repository", "repo"),
    "索引": ("index", "indexer"),
    "依存": ("dependency", "import"),
    "計画": ("plan", "planner"),
    "読む": ("read", "reader"),
    "読取": ("read", "reader"),
    "読み取り": ("read", "reader"),
    "修正": ("fix", "repair", "update"),
    "変更": ("change", "update", "modify"),
    "追加": ("add", "create"),
    "実装": ("implement", "code"),
    "検証": ("verify", "verification", "test"),
    "テスト": ("test", "tests"),
    "コード": ("code", "generator"),
}


@dataclass(frozen=True)
class SourceSlice:
    path: str
    language: str
    sha256: str
    score: float
    reasons: tuple[str, ...]
    excerpt: str
    excerpt_bytes: int
    stale: bool = False


@dataclass(frozen=True)
class RepositoryReadContext:
    goal: str
    repository_digest: str
    files: tuple[SourceSlice, ...]
    omitted_files: int
    index_errors: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryReader:
    """Bounded, read-only source selector over a V87.65 RepositoryIndex.

    The reader never imports or executes project code and never writes files.
    It ranks existing files/symbols, expands one bounded dependency neighborhood,
    verifies indexed hashes before exposing source, and enforces byte/file caps.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        index: RepositoryIndex | None = None,
        max_files: int = 8,
        max_total_bytes: int = 120_000,
        max_file_bytes: int = 30_000,
        dependency_hops: int = 1,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.root}")
        if not 1 <= int(max_files) <= 32:
            raise ValueError("max_files must be in [1, 32]")
        if int(max_total_bytes) <= 0 or int(max_file_bytes) <= 0:
            raise ValueError("byte limits must be positive")
        if not 0 <= int(dependency_hops) <= 2:
            raise ValueError("dependency_hops must be in [0, 2]")
        self.max_files = int(max_files)
        self.max_total_bytes = int(max_total_bytes)
        self.max_file_bytes = min(int(max_file_bytes), self.max_total_bytes)
        self.dependency_hops = int(dependency_hops)
        self.index = index or RepositoryIndexer(self.root).build()
        if Path(self.index.root).resolve() != self.root:
            raise ValueError("index root does not match reader root")
        self._by_path = {rec.path: rec for rec in self.index.files}

    @property
    def repository_digest(self) -> str:
        payload = "\n".join(
            f"{rec.path}\0{rec.size}\0{rec.sha256}\0{rec.parse_status}"
            for rec in sorted(self.index.files, key=lambda x: x.path)
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    def read(self, goal: str) -> RepositoryReadContext:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        tokens = _query_tokens(goal)
        ranked = self._rank(tokens, goal)
        selected = self._select_paths(ranked)

        out: list[SourceSlice] = []
        used = 0
        for path, score, reasons in selected:
            if len(out) >= self.max_files or used >= self.max_total_bytes:
                break
            rec = self._by_path[path]
            budget = min(self.max_file_bytes, self.max_total_bytes - used)
            source = self._source_slice(rec, tokens, budget, score, reasons)
            out.append(source)
            used += source.excerpt_bytes

        return RepositoryReadContext(
            goal=goal,
            repository_digest=self.repository_digest,
            files=tuple(out),
            omitted_files=max(0, len(ranked) - len(out)),
            index_errors=tuple(self.index.errors),
        )

    def _rank(self, tokens: tuple[str, ...], goal: str) -> list[tuple[str, float, tuple[str, ...]]]:
        low_goal = goal.casefold().replace("\\", "/")
        ranked: list[tuple[str, float, tuple[str, ...]]] = []
        for rec in self.index.files:
            path_low = rec.path.casefold()
            score = 0.0
            reasons: list[str] = []
            if rec.path.casefold() in low_goal:
                score += 30.0
                reasons.append("exact_path")

            symbol_text = " ".join(
                f"{sym.name} {sym.signature} {sym.parent or ''}"
                for sym in rec.symbols
            ).casefold()
            import_text = " ".join(rec.imports).casefold()
            for token in tokens:
                if token in path_low:
                    score += 8.0
                    reasons.append(f"path:{token}")
                if token in symbol_text:
                    score += 5.0
                    reasons.append(f"symbol:{token}")
                if token in import_text:
                    score += 2.0
                    reasons.append(f"import:{token}")

            if score > 0:
                ranked.append((rec.path, score, tuple(dict.fromkeys(reasons))))
        ranked.sort(key=lambda row: (-row[1], row[0]))
        return ranked

    def _select_paths(
        self,
        ranked: list[tuple[str, float, tuple[str, ...]]],
    ) -> list[tuple[str, float, tuple[str, ...]]]:
        if not ranked:
            return []
        reserve = 2 if self.dependency_hops and self.max_files >= 4 else 0
        primary = ranked[: max(1, self.max_files - reserve)]
        selected: dict[str, tuple[float, tuple[str, ...]]] = {
            path: (score, reasons) for path, score, reasons in primary
        }
        if not self.dependency_hops:
            return [(p, *selected[p]) for p in selected]

        adjacency: dict[str, set[str]] = {}
        for edge in self.index.dependencies:
            adjacency.setdefault(edge.source, set()).add(edge.target)
            adjacency.setdefault(edge.target, set()).add(edge.source)

        frontier = list(selected)
        for hop in range(self.dependency_hops):
            next_frontier: list[str] = []
            for path in frontier:
                for neighbor in sorted(adjacency.get(path, ())):
                    if neighbor in selected or neighbor not in self._by_path:
                        continue
                    if len(selected) >= self.max_files:
                        break
                    selected[neighbor] = (
                        max(0.25, selected[path][0] * 0.10),
                        (f"dependency_hop:{hop + 1}:{path}",),
                    )
                    next_frontier.append(neighbor)
                if len(selected) >= self.max_files:
                    break
            frontier = next_frontier
            if not frontier or len(selected) >= self.max_files:
                break

        rows = [(path, score, reasons) for path, (score, reasons) in selected.items()]
        rows.sort(key=lambda row: (-row[1], row[0]))
        return rows[: self.max_files]

    def _source_slice(
        self,
        rec: FileRecord,
        tokens: tuple[str, ...],
        budget: int,
        score: float,
        reasons: tuple[str, ...],
    ) -> SourceSlice:
        path = (self.root / rec.path).resolve()
        if not _inside(self.root, path) or not path.is_file() or path.is_symlink():
            return SourceSlice(
                rec.path, rec.language, rec.sha256, score,
                reasons + ("source_unavailable",), "", 0, True,
            )

        actual = _sha256_file(path)
        if actual != rec.sha256:
            return SourceSlice(
                rec.path, rec.language, rec.sha256, score,
                reasons + ("stale_hash",), "", 0, True,
            )

        raw = _read_prefix(path, budget)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return SourceSlice(
                    rec.path, rec.language, rec.sha256, score,
                    reasons + ("non_utf8",), "", 0, False,
                )

        excerpt = _focus_excerpt(text, rec, tokens)
        excerpt = _truncate_utf8(excerpt, budget)
        return SourceSlice(
            path=rec.path,
            language=rec.language,
            sha256=rec.sha256,
            score=round(score, 3),
            reasons=reasons,
            excerpt=excerpt,
            excerpt_bytes=len(excerpt.encode("utf-8")),
            stale=False,
        )


def _query_tokens(text: str) -> tuple[str, ...]:
    low = text.casefold()
    found = re.findall(r"[0-9a-z_./-]{2,}|[ぁ-んァ-ヶ一-龯]{2,}", low)
    expanded: list[str] = []
    for token in found:
        expanded.append(token)
        for key, aliases in QUERY_ALIASES.items():
            if key in token:
                expanded.extend(aliases)
    return tuple(dict.fromkeys(x for x in expanded if len(x) >= 2))


def _focus_excerpt(text: str, rec: FileRecord, tokens: tuple[str, ...]) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    matching = [
        sym for sym in rec.symbols
        if any(
            token in sym.name.casefold() or token in sym.signature.casefold()
            for token in tokens
        )
    ]
    if not matching:
        return "\n".join(lines[:160]) + ("\n" if lines else "")

    ranges: list[tuple[int, int]] = []
    for sym in matching[:4]:
        start = max(0, sym.line - 4)
        end_line = sym.end_line or sym.line
        end = min(len(lines), end_line + 3)
        ranges.append((start, end))

    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 2:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    chunks = []
    for start, end in merged:
        chunks.append(f"# {rec.path}:L{start + 1}-L{end}")
        chunks.extend(lines[start:end])
    return "\n".join(chunks).rstrip() + "\n"


def _read_prefix(path: Path, limit: int) -> bytes:
    if limit <= 0:
        return b""
    with path.open("rb") as fh:
        return fh.read(limit)


def _sha256_file(path: Path, chunk_size: int = 128 * 1024) -> str:
    h = sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _truncate_utf8(text: str, limit: int) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    clipped = raw[:limit]
    while clipped:
        try:
            return clipped.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return ""


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
