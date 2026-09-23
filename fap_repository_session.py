from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
import re
from threading import RLock
from typing import Iterable

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[0-9A-Za-z_.:-]{1,128}$")


@dataclass(frozen=True)
class RepositorySessionState:
    session_id: str
    repository_digest: str
    plan_id: str
    state: str
    paths: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositorySessionLedger:
    """Content-free continuity for multi-turn repository coding.

    Only hashes, state and bounded relative paths are retained. Source text,
    generated edits, diffs, provider messages and verification output are never
    stored here.
    """

    def __init__(self, *, max_sessions: int = 128, max_paths: int = 32) -> None:
        if not 1 <= int(max_sessions) <= 4096:
            raise ValueError("max_sessions must be in [1, 4096]")
        if not 1 <= int(max_paths) <= 64:
            raise ValueError("max_paths must be in [1, 64]")
        self.max_sessions = int(max_sessions)
        self.max_paths = int(max_paths)
        self._rows: OrderedDict[str, RepositorySessionState] = OrderedDict()
        self._lock = RLock()

    def record(
        self,
        session_id: str,
        repository_digest: str,
        plan_id: str,
        *,
        state: str,
        paths: Iterable[str],
    ) -> RepositorySessionState:
        sid = self._safe_id(session_id, "session_id")
        digest = str(repository_digest or "").strip().lower()
        pid = str(plan_id or "").strip().lower()
        if not _HEX64.fullmatch(digest) or not _HEX64.fullmatch(pid):
            raise ValueError("repository_digest and plan_id must be lowercase SHA-256")
        state_value = self._safe_id(state, "state")

        kept: list[str] = []
        for path in paths:
            value = self._normalize_path(path)
            if value and value not in kept:
                kept.append(value)
            if len(kept) >= self.max_paths:
                break

        row = RepositorySessionState(
            session_id=sid,
            repository_digest=digest,
            plan_id=pid,
            state=state_value,
            paths=tuple(kept),
        )
        with self._lock:
            self._rows.pop(sid, None)
            self._rows[sid] = row
            while len(self._rows) > self.max_sessions:
                self._rows.popitem(last=False)
        return row

    def snapshot(self, session_id: str) -> RepositorySessionState | None:
        sid = self._safe_id(session_id, "session_id")
        with self._lock:
            row = self._rows.pop(sid, None)
            if row is None:
                return None
            self._rows[sid] = row
            return row

    def preferred_paths(
        self,
        session_id: str,
        repository_digest: str,
    ) -> tuple[str, ...]:
        digest = str(repository_digest or "").strip().lower()
        if not _HEX64.fullmatch(digest):
            return ()
        row = self.snapshot(session_id)
        if row is None or row.repository_digest != digest:
            return ()
        return row.paths

    def clear(self, session_id: str) -> None:
        sid = self._safe_id(session_id, "session_id")
        with self._lock:
            self._rows.pop(sid, None)

    @staticmethod
    def _safe_id(value: str, name: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_ID.fullmatch(text):
            raise ValueError(f"{name} contains unsupported characters")
        return text

    @staticmethod
    def _normalize_path(path: object) -> str:
        value = str(path or "").strip().replace("\\", "/")
        if not value or len(value) > 512 or value.startswith("/"):
            return ""
        parts = value.split("/")
        if ".." in parts or ".git" in parts:
            return ""
        return value
