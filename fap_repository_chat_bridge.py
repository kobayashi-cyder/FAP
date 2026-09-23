from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping


_PATH = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.(?:py|js|ts|tsx|jsx|json|ya?ml|toml|md|sh|ps1|cmd))(?![A-Za-z0-9_./-])",
    re.I,
)
_CODING = re.compile(
    r"(fix|repair|update|modify|implement|refactor|create|delete|test|code|"
    r"修正|変更|更新|実装|追加|削除|テスト|コード)",
    re.I,
)
_SAFE_BRANCH = re.compile(r"^[0-9A-Za-z._/-]{1,200}$")


@dataclass(frozen=True)
class ChatCodingRequest:
    contract: str
    goal: str
    branch: str
    base_commit: str
    history_digest: str
    file_hints: tuple[str, ...]
    turns_considered: int

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryChatBridge:
    """Convert chat context into a bounded, content-minimized coding request."""

    CONTRACT = "fap.repository.chat_bridge.v1"

    @classmethod
    def claims(cls, text: str) -> bool:
        value = str(text or "").strip()
        return bool(value and _CODING.search(value))

    def build(
        self,
        current_text: str,
        *,
        history: Iterable[Mapping[str, object] | str] = (),
        branch: str,
        base_commit: str = "",
        max_turns: int = 12,
        max_goal_chars: int = 20_000,
        max_file_hints: int = 32,
    ) -> ChatCodingRequest:
        goal = str(current_text or "").strip()
        if not goal:
            raise ValueError("current_text is required")
        if len(goal) > int(max_goal_chars):
            raise ValueError("current_text exceeds max_goal_chars")
        branch = _safe_branch(branch)
        base_commit = str(base_commit or "").strip()
        if base_commit and not re.fullmatch(r"[0-9a-fA-F]{7,64}", base_commit):
            raise ValueError("base_commit must be hexadecimal")

        rows = tuple(history)
        if not 0 <= int(max_turns) <= 100:
            raise ValueError("max_turns must be in [0, 100]")
        considered = rows[-int(max_turns):] if max_turns else ()
        texts = tuple(_message_text(row) for row in considered)
        digest_payload = json.dumps(
            texts,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        history_digest = sha256(digest_payload.encode("utf-8")).hexdigest()

        hints: list[str] = []
        for text in (*texts, goal):
            for raw in _PATH.findall(text):
                path = raw.replace("\\", "/").lstrip("./")
                if ".." in path.split("/") or path.startswith(".git/"):
                    continue
                if path not in hints:
                    hints.append(path)
                if len(hints) >= int(max_file_hints):
                    break
            if len(hints) >= int(max_file_hints):
                break

        return ChatCodingRequest(
            contract=self.CONTRACT,
            goal=goal,
            branch=branch,
            base_commit=base_commit,
            history_digest=history_digest,
            file_hints=tuple(hints),
            turns_considered=len(considered),
        )


def _message_text(row: Mapping[str, object] | str) -> str:
    if isinstance(row, str):
        return row[:20_000]
    if isinstance(row, Mapping):
        for key in ("content", "text", "reply", "observation"):
            value = row.get(key)
            if isinstance(value, str) and value:
                return value[:20_000]
    return ""


def _safe_branch(raw: str) -> str:
    value = str(raw or "").strip()
    if not _SAFE_BRANCH.fullmatch(value):
        raise ValueError("branch contains invalid characters")
    if value in {"main", "master"}:
        raise ValueError("chat coding requests require a non-main branch")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise ValueError("branch shape is invalid")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("branch shape is invalid")
    return value
