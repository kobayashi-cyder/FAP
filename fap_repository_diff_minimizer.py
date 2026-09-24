from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Iterable

from fap_repository_executor import FileEdit


@dataclass(frozen=True)
class DiffFootprint:
    path: str
    operation: str
    before_bytes: int
    after_bytes: int
    changed_lines: int
    similarity: float
    byte_delta: int
    changed_bytes: int
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CandidateFootprint:
    files: tuple[DiffFootprint, ...]
    total_changed_lines: int
    total_byte_delta: int
    total_changed_bytes: int
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryDiffMinimizer:
    """Rank verified FileEdit candidates by changed surface without writing files."""

    VERSION = "fap.repository.diff_minimizer.v1"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")

    def measure(self, edits: Iterable[FileEdit]) -> CandidateFootprint:
        rows = tuple(edits)
        if not rows:
            raise ValueError("at least one edit is required")
        footprints: list[DiffFootprint] = []
        seen: set[str] = set()
        for edit in rows:
            rel = self._validated_relpath(edit.path)
            if rel in seen:
                raise ValueError(f"duplicate edit path: {rel}")
            seen.add(rel)
            footprints.append(self._measure_file(edit, rel))
        return CandidateFootprint(
            files=tuple(footprints),
            total_changed_lines=sum(x.changed_lines for x in footprints),
            total_byte_delta=sum(abs(x.byte_delta) for x in footprints),
            total_changed_bytes=sum(x.changed_bytes for x in footprints),
            score=round(sum(x.score for x in footprints), 6),
        )

    def choose_smallest(self, candidates: Iterable[Iterable[FileEdit]]) -> tuple[int, CandidateFootprint]:
        measured = [self.measure(candidate) for candidate in candidates]
        if not measured:
            raise ValueError("at least one candidate is required")
        index = min(range(len(measured)), key=lambda i: (
            measured[i].score, measured[i].total_changed_lines,
            measured[i].total_changed_bytes, measured[i].total_byte_delta,
            len(measured[i].files), i,
        ))
        return index, measured[index]

    def _validated_relpath(self, value: str) -> str:
        if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
            raise ValueError("invalid repository-relative edit path")
        pure = PurePosixPath(value)
        if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
            raise ValueError(f"edit path escapes repository: {value}")
        current = self.root
        for part in pure.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"symlink path component rejected: {value}")
            if not current.exists():
                break
        candidate = (self.root / pure).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"edit path escapes repository: {value}") from exc
        return pure.as_posix()

    def _measure_file(self, edit: FileEdit, rel: str) -> DiffFootprint:
        path = self.root / rel
        if edit.operation == "create":
            if path.exists() or path.is_symlink():
                raise ValueError(f"create target already exists: {rel}")
            if edit.before_sha256:
                raise ValueError(f"create edit must not include before hash: {rel}")
            if edit.content is None:
                raise ValueError(f"create edit requires content: {rel}")
            before, after = "", edit.content
        elif edit.operation == "delete":
            before = self._read_fresh(path, edit.before_sha256, rel)
            if edit.content is not None:
                raise ValueError(f"delete edit must not include content: {rel}")
            after = ""
        elif edit.operation == "modify":
            before = self._read_fresh(path, edit.before_sha256, rel)
            if edit.content is None:
                raise ValueError(f"modify edit requires content: {rel}")
            after = edit.content
        else:
            raise ValueError(f"unsupported edit operation: {edit.operation}")
        try:
            before_raw = before.encode("utf-8", errors="strict")
            after_raw = after.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(f"edit content is not UTF-8 encodable: {rel}") from exc
        before_lines, after_lines = before.splitlines(keepends=True), after.splitlines(keepends=True)
        matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
        changed = sum(max(i2-i1, j2-j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")
        similarity = matcher.ratio()
        byte_matcher = SequenceMatcher(a=before_raw, b=after_raw, autojunk=False)
        changed_bytes = sum(max(i2-i1, j2-j1) for tag, i1, i2, j1, j2 in byte_matcher.get_opcodes() if tag != "equal")
        byte_delta = len(after_raw) - len(before_raw)
        score = changed + changed_bytes / 4096.0 + (1.0 - similarity)
        return DiffFootprint(rel, edit.operation, len(before_raw), len(after_raw), changed,
                             round(similarity, 6), byte_delta, changed_bytes, round(score, 6))

    @staticmethod
    def _read_fresh(path: Path, expected_sha: str, rel: str) -> str:
        if not expected_sha or len(expected_sha) != 64:
            raise ValueError(f"invalid before hash: {rel}")
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"source unavailable: {rel}")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != expected_sha:
            raise ValueError(f"STALE_EDIT: source hash changed: {rel}")
        try:
            return raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"source is not UTF-8: {rel}") from exc
