from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable


_SAFE_BRANCH = re.compile(r"^[0-9A-Za-z._/-]{1,200}$")
_SAFE_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RepositorySessionHandoff:
    contract: str
    branch: str
    base_commit: str
    plan_id: str
    repository_digest: str
    paths: tuple[str, ...]
    sequence: int
    checksum: str

    def to_dict(self) -> dict:
        return asdict(self)


class RepositorySessionHandoffCodec:
    """Content-free, bounded handoff token for repository coding sessions.

    The checksum detects accidental corruption. It is not an authentication
    primitive and must not be treated as proof that an untrusted sender created
    the token.
    """

    CONTRACT = "fap.repository.session_handoff.v1"

    def __init__(
        self,
        *,
        max_paths: int = 32,
        max_token_chars: int = 20_000,
    ) -> None:
        if not 1 <= int(max_paths) <= 256:
            raise ValueError("max_paths must be in [1, 256]")
        if not 512 <= int(max_token_chars) <= 200_000:
            raise ValueError("max_token_chars must be in [512, 200000]")
        self.max_paths = int(max_paths)
        self.max_token_chars = int(max_token_chars)

    def encode(
        self,
        *,
        branch: str,
        base_commit: str,
        plan_id: str,
        repository_digest: str,
        paths: Iterable[str] = (),
        sequence: int = 0,
    ) -> str:
        branch = _branch(branch)
        base_commit = _hex(base_commit, "base_commit", minimum=7, allow_empty=True)
        plan_id = _hex(plan_id, "plan_id", minimum=64, allow_empty=False)
        repository_digest = _hex(
            repository_digest,
            "repository_digest",
            minimum=64,
            allow_empty=False,
        )
        if int(sequence) < 0:
            raise ValueError("sequence must be non-negative")

        clean_paths = tuple(dict.fromkeys(_path(x) for x in paths))
        if len(clean_paths) > self.max_paths:
            raise ValueError("handoff path limit exceeded")

        payload = {
            "contract": self.CONTRACT,
            "branch": branch,
            "base_commit": base_commit,
            "plan_id": plan_id,
            "repository_digest": repository_digest,
            "paths": clean_paths,
            "sequence": int(sequence),
        }
        checksum = _checksum(payload)
        token = json.dumps(
            {**payload, "checksum": checksum},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(token) > self.max_token_chars:
            raise ValueError("handoff token size limit exceeded")
        return token

    def decode(self, token: str) -> RepositorySessionHandoff:
        raw_token = str(token or "")
        if not raw_token:
            raise ValueError("handoff token is empty")
        if len(raw_token) > self.max_token_chars:
            raise ValueError("handoff token size limit exceeded")
        try:
            row = json.loads(raw_token)
        except json.JSONDecodeError as exc:
            raise ValueError("handoff token is not valid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError("handoff token root must be an object")
        if row.get("contract") != self.CONTRACT:
            raise ValueError("unsupported handoff contract")

        supplied = str(row.get("checksum") or "").strip().casefold()
        if not _SAFE_CHECKSUM.fullmatch(supplied):
            raise ValueError("handoff checksum is invalid")

        raw_paths = row.get("paths", ())
        if not isinstance(raw_paths, (list, tuple)):
            raise ValueError("handoff paths must be an array")
        if len(raw_paths) > self.max_paths:
            raise ValueError("handoff path limit exceeded")

        try:
            sequence = int(row.get("sequence", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("sequence must be an integer") from exc
        if sequence < 0:
            raise ValueError("sequence must be non-negative")

        clean_paths = tuple(dict.fromkeys(_path(x) for x in raw_paths))
        payload = {
            "contract": self.CONTRACT,
            "branch": _branch(row.get("branch")),
            "base_commit": _hex(
                row.get("base_commit"),
                "base_commit",
                minimum=7,
                allow_empty=True,
            ),
            "plan_id": _hex(
                row.get("plan_id"),
                "plan_id",
                minimum=64,
                allow_empty=False,
            ),
            "repository_digest": _hex(
                row.get("repository_digest"),
                "repository_digest",
                minimum=64,
                allow_empty=False,
            ),
            "paths": clean_paths,
            "sequence": sequence,
        }
        expected = _checksum(payload)
        if supplied != expected:
            raise ValueError("handoff checksum mismatch")
        return RepositorySessionHandoff(
            **payload,
            checksum=expected,
        )


def _checksum(payload: dict) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _branch(raw: object) -> str:
    value = str(raw or "").strip()
    if (
        not _SAFE_BRANCH.fullmatch(value)
        or value in {"main", "master"}
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("handoff requires a safe non-main branch")
    return value


def _hex(
    raw: object,
    label: str,
    *,
    minimum: int,
    allow_empty: bool,
) -> str:
    value = str(raw or "").strip()
    if allow_empty and not value:
        return ""
    if not re.fullmatch(rf"[0-9a-fA-F]{{{minimum},64}}", value):
        raise ValueError(f"{label} must be hexadecimal")
    return value.lower()


def _path(raw: object) -> str:
    value = str(raw or "").strip().replace("\\", "/").lstrip("./")
    parts = value.split("/")
    if not value or any(part in {"", ".", "..", ".git"} for part in parts):
        raise ValueError("invalid handoff path")
    return value
