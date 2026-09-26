from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List


MODES = ("brief", "normal", "rich", "verbose")


@dataclass(frozen=True)
class ChatTurn:
    role: str
    text: str


class ChatSession:
    """Bounded chat-session adapter for FAP responders.

    This is an interaction/state surface, not a language model. It preserves
    bounded recent context, exposes the four historical FAP response modes,
    and leaves semantic generation to the supplied responder.
    """

    def __init__(self, *, mode: str = "rich", max_turns: int = 24):
        if mode not in MODES:
            raise ValueError("unsupported chat mode")
        if max_turns < 2:
            raise ValueError("max_turns must be >= 2")
        self.mode = mode
        self.max_turns = int(max_turns)
        self.turns: List[ChatTurn] = []

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError("unsupported chat mode")
        self.mode = mode

    def context_text(self) -> str:
        return "\n".join(f"{t.role}: {t.text}" for t in self.turns[-self.max_turns:])

    def submit(self, text: str, responder: Callable[[str, str, str], str]) -> str:
        user_text = str(text).strip()
        if not user_text:
            raise ValueError("chat input is required")

        if user_text.startswith(":"):
            command = user_text[1:].strip().lower()
            if command in MODES:
                self.set_mode(command)
                return f"mode={self.mode}"

        prior_context = self.context_text()
        response = str(responder(user_text, prior_context, self.mode)).strip()
        if not response:
            raise ValueError("responder returned empty text")

        self.turns.append(ChatTurn("user", user_text))
        self.turns.append(ChatTurn("assistant", response))
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        return response
