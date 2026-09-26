from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Iterable

from fap_repository_index import RepositoryIndex, RepositoryIndexer


@dataclass(frozen=True)
class ContextCandidate:
    path: str
    score: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryContextFusion:
    """Fuse multiple coding queries into one bounded repository ranking."""

    VERSION = "fap.repository.context_fusion.v1"

    def __init__(
        self,
        root: str | Path,
        *,
        index: RepositoryIndex | None = None,
        max_results: int = 16,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not 1 <= int(max_results) <= 64:
            raise ValueError("max_results must be in [1, 64]")
        self.max_results = int(max_results)
        self.index = index or RepositoryIndexer(self.root).build()
        if Path(self.index.root).resolve() != self.root:
            raise ValueError("index root does not match context fusion root")

    def rank(self, queries: Iterable[str]) -> tuple[ContextCandidate, ...]:
        query_rows = tuple(str(x or "").strip() for x in queries)
        query_rows = tuple(x for x in query_rows if x)
        if not query_rows:
            raise ValueError("at least one non-empty query is required")

        query_tokens = tuple(_tokens(q) for q in query_rows)
        out: list[ContextCandidate] = []
        for rec in self.index.files:
            path_low = rec.path.casefold()
            symbol_text = " ".join(
                f"{sym.name} {sym.signature} {sym.parent or ''}"
                for sym in rec.symbols
            ).casefold()
            import_text = " ".join(rec.imports).casefold()

            score = 0.0
            reasons: list[str] = []
            for q_index, (query, tokens) in enumerate(zip(query_rows, query_tokens)):
                low_query = query.casefold().replace("\\", "/")
                local = 0.0
                if rec.path.casefold() in low_query:
                    local += 40.0
                    reasons.append(f"q{q_index}:exact_path")
                for token in tokens:
                    if token in path_low:
                        local += 8.0
                        reasons.append(f"q{q_index}:path:{token}")
                    if token in symbol_text:
                        local += 5.0
                        reasons.append(f"q{q_index}:symbol:{token}")
                    if token in import_text:
                        local += 2.0
                        reasons.append(f"q{q_index}:import:{token}")
                # Reward support across queries rather than letting one verbose
                # query completely dominate the fused ranking.
                if local > 0:
                    score += min(local, 60.0)

            if score > 0:
                out.append(
                    ContextCandidate(
                        path=rec.path,
                        score=round(score, 3),
                        reasons=tuple(dict.fromkeys(reasons)),
                    )
                )

        out.sort(key=lambda row: (-row.score, row.path))
        return tuple(out[: self.max_results])


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            token
            for token in re.findall(r"[A-Za-z0-9_]{2,}", text.casefold())
            if token not in {"the", "and", "with", "from", "into", "then"}
        )
    )
