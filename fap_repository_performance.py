from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from fap_repository_index import RepositoryIndex, RepositoryIndexer


@dataclass(frozen=True)
class IndexCacheStats:
    hits: int
    misses: int
    bypasses: int


class RepositoryIndexCache:
    """In-memory cache for repeated clean Git repository indexing.

    Cache reuse is allowed only when HEAD is unchanged and the working tree is
    clean. Dirty repositories bypass the cache entirely so repository-coding
    freshness semantics remain conservative.
    """

    VERSION = "fap.repository.index_cache.v1"

    def __init__(
        self,
        root: str | Path,
        *,
        builder: Callable[[], RepositoryIndex] | None = None,
        git_timeout_sec: int = 10,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not 1 <= int(git_timeout_sec) <= 60:
            raise ValueError("git_timeout_sec must be in [1, 60]")
        self.git_timeout_sec = int(git_timeout_sec)
        self.builder = builder or (lambda: RepositoryIndexer(self.root).build())
        self._head: str | None = None
        self._index: RepositoryIndex | None = None
        self._hits = 0
        self._misses = 0
        self._bypasses = 0

    @property
    def stats(self) -> IndexCacheStats:
        return IndexCacheStats(self._hits, self._misses, self._bypasses)

    def get(self) -> RepositoryIndex:
        head, clean = self._git_state()
        if not clean:
            self._bypasses += 1
            return self.builder()

        if self._index is not None and self._head == head:
            self._hits += 1
            return self._index

        index = self.builder()
        self._index = index
        self._head = head
        self._misses += 1
        return index

    def invalidate(self) -> None:
        self._head = None
        self._index = None

    def _git_state(self) -> tuple[str, bool]:
        head = self._git("rev-parse", "--verify", "HEAD").strip()
        status = self._git(
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        return head, not bool(status.strip())

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=self.git_timeout_sec,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git command failed: {' '.join(args)}")
        return proc.stdout
