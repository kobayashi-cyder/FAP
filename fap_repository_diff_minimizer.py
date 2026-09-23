from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
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
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CandidateFootprint:
    files: tuple[DiffFootprint, ...]
    total_changed_lines: int
    total_byte_delta: int
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryDiffMinimizer:
    """Measure candidate edit surface without applying repository writes.

    Lower scores are smaller candidates. Existing-file edits are protected by
    their before_sha256 precondition so stale candidates cannot be ranked as if
    they still matched the repository.
    """

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
            if edit.path in seen:
                raise ValueError(f"duplicate edit path: {edit.path}")
            seen.add(edit.path)
            footprints.append(self._measure_file(edit))
        return CandidateFootprint(
            files=tuple(footprints),
            total_changed_lines=sum(x.changed_lines for x in footprints),
            total_byte_delta=sum(abs(x.byte_delta) for x in footprints),
            score=round(sum(x.score for x in footprints), 6),
        )

    def choose_smallest(
        self,
        candidates: Iterable[Iterable[FileEdit]],
    ) -> tuple[int, CandidateFootprint]:
        measured = [self.measure(candidate) for candidate in candidates]
        if not measured:
            raise ValueError("at least one candidate is required")
        index = min(
            range(len(measured)),
            key=lambda i: (
                measured[i].score,
                measured[i].total_changed_lines,
                measured[i].total_byte_delta,
                len(measured[i].files),
                i,
            ),
        )
        return index, measured[index]

    def _measure_file(self, edit: FileEdit) -> DiffFootprint:
        path = self.root / edit.path
        if edit.operation == "create":
            if path.exists():
                raise ValueError(f"create target already exists: {edit.path}")
            before = ""
            after = edit.content or ""
        elif edit.operation == "delete":
            before = self._read_fresh(path, edit.before_sha256, edit.path)
            if edit.content is not None:
                raise ValueError(f"delete edit must not include content: {edit.path}")
            after = ""
        elif edit.operation == "modify":
            before = self._read_fresh(path, edit.before_sha256, edit.path)
            if edit.content is None:
                raise ValueError(f"modify edit requires content: {edit.path}")
            after = edit.content
        else:
            raise ValueError(f"unsupported edit operation: {edit.operation}")

        before_lines = before.splitlines()
        after_lines = after.splitlines()
        matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
        changed = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                changed += max(i2 - i1, j2 - j1)
        similarity = matcher.ratio()
        before_bytes = len(before.encode("utf-8"))
        after_bytes = len(after.encode("utf-8"))
        byte_delta = after_bytes - before_bytes
        # Line churn dominates; byte churn and number of files break close ties.
        score = changed + (abs(byte_delta) / 4096.0) + (1.0 - similarity)
        return DiffFootprint(
            path=edit.path,
            operation=edit.operation,
            before_bytes=before_bytes,
            after_bytes=after_bytes,
            changed_lines=changed,
            similarity=round(similarity, 6),
            byte_delta=byte_delta,
            score=round(score, 6),
        )

    @staticmethod
    def _read_fresh(path: Path, expected_sha: str, rel: str) -> str:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"source unavailable: {rel}")
        raw = path.read_bytes()
        actual = sha256(raw).hexdigest()
        if actual != expected_sha:
            raise ValueError(f"STALE_EDIT: source hash changed: {rel}")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"source is not UTF-8: {rel}") from exc
