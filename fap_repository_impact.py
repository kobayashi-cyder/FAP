from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from fap_repository_index import RepositoryIndex, RepositoryIndexer


@dataclass(frozen=True)
class ImpactedPath:
    path: str
    distance: int
    reason: str


@dataclass(frozen=True)
class RepositoryImpactReport:
    version: str
    seeds: tuple[str, ...]
    impacted: tuple[ImpactedPath, ...]
    test_paths: tuple[str, ...]
    truncated: bool
    index_errors: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryImpactAnalyzer:
    """Bounded reverse-dependency analysis for repository coding changes."""

    VERSION = "fap.repository.impact.v1"

    def __init__(
        self,
        root: str | Path,
        *,
        index: RepositoryIndex | None = None,
        max_depth: int = 2,
        max_impacted: int = 128,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not 0 <= int(max_depth) <= 4:
            raise ValueError("max_depth must be in [0, 4]")
        if not 1 <= int(max_impacted) <= 1024:
            raise ValueError("max_impacted must be in [1, 1024]")
        self.max_depth = int(max_depth)
        self.max_impacted = int(max_impacted)
        self.index = index or RepositoryIndexer(self.root).build()
        if Path(self.index.root).resolve() != self.root:
            raise ValueError("index root does not match analyzer root")

        self.known_paths = frozenset(row.path for row in self.index.files)
        reverse: dict[str, set[str]] = {}
        for edge in self.index.dependencies:
            if edge.source not in self.known_paths or edge.target not in self.known_paths:
                continue
            reverse.setdefault(edge.target, set()).add(edge.source)
        self._reverse = {
            target: tuple(sorted(sources))
            for target, sources in reverse.items()
        }

    def analyze(self, paths: Iterable[str]) -> RepositoryImpactReport:
        seeds = tuple(dict.fromkeys(_safe_relative_path(path) for path in paths))
        if not seeds:
            raise ValueError("at least one seed path is required")
        if len(seeds) > self.max_impacted:
            raise ValueError("seed path count exceeds impact limit")

        missing = tuple(path for path in seeds if path not in self.known_paths)
        if missing:
            raise ValueError("unknown repository paths: " + ", ".join(missing))

        queue = deque((path, 0) for path in seeds)
        distances = {path: 0 for path in seeds}
        reasons = {path: "changed" for path in seeds}
        truncated = False

        while queue:
            current, distance = queue.popleft()
            if distance >= self.max_depth:
                continue
            for dependent in self._reverse.get(current, ()):
                if dependent in distances:
                    continue
                if len(distances) >= self.max_impacted:
                    truncated = True
                    queue.clear()
                    break
                next_distance = distance + 1
                distances[dependent] = next_distance
                reasons[dependent] = (
                    f"reverse_dependency:{current}:distance={next_distance}"
                )
                queue.append((dependent, next_distance))

        impacted = tuple(
            ImpactedPath(
                path=path,
                distance=distances[path],
                reason=reasons[path],
            )
            for path in sorted(
                distances,
                key=lambda value: (distances[value], value),
            )
        )
        tests = tuple(
            item.path
            for item in impacted
            if _is_python_test_path(item.path)
        )
        return RepositoryImpactReport(
            version=self.VERSION,
            seeds=seeds,
            impacted=impacted,
            test_paths=tests,
            truncated=truncated,
            index_errors=tuple(self.index.errors),
        )


def _safe_relative_path(raw: object) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or any(part in {"", ".", "..", ".git"} for part in posix.parts)
        or "\x00" in value
    ):
        raise ValueError("path must be a safe relative repository path")
    return posix.as_posix()


def _is_python_test_path(path: str) -> bool:
    value = str(path).replace("\\", "/")
    if not value.startswith("tests/") or not value.endswith(".py"):
        return False
    name = PurePosixPath(value).name
    return name.startswith("test_") or name.endswith("_test.py")
