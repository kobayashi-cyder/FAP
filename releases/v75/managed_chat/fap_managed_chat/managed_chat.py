from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fap_interaction.chat import ChatSession, ChatTurn, MODES


@dataclass(frozen=True)
class ManagedChatStatus:
    mode: str
    turns: int
    exchanges: int
    context_chars: int
    max_context_chars: int
    max_exchanges: int


def _clip_middle(text: str, limit: int) -> str:
    if limit < 0:
        raise ValueError("clip limit must be non-negative")
    if len(text) <= limit:
        return text
    if limit == 0:
        return ""
    marker = "…"
    if limit <= len(marker):
        return marker[:limit]
    remaining = limit - len(marker)
    left = (remaining + 1) // 2
    right = remaining // 2
    return text[:left] + marker + (text[-right:] if right else "")


class ManagedChatSession:
    """Bounded chat controls layered on the V69 ChatSession.

    Full responses are returned to the caller. Stored history is bounded separately so a
    single large response does not permanently inflate context memory.
    """

    def __init__(
        self,
        *,
        mode: str = "rich",
        max_exchanges: int = 12,
        max_context_chars: int = 12000,
        max_input_chars: int = 4000,
        max_stored_assistant_chars: int = 6000,
    ):
        if mode not in MODES:
            raise ValueError("unsupported chat mode")
        if max_exchanges < 1:
            raise ValueError("max_exchanges must be >= 1")
        if max_context_chars < 64:
            raise ValueError("max_context_chars must be >= 64")
        if not (1 <= max_input_chars <= max_context_chars):
            raise ValueError("max_input_chars must fit within context budget")
        if not (1 <= max_stored_assistant_chars <= max_context_chars):
            raise ValueError("max_stored_assistant_chars must fit within context budget")

        self.max_exchanges = int(max_exchanges)
        self.max_context_chars = int(max_context_chars)
        self.max_input_chars = int(max_input_chars)
        self.max_stored_assistant_chars = int(max_stored_assistant_chars)
        self.session = ChatSession(mode=mode, max_turns=max_exchanges * 2)

    @property
    def mode(self) -> str:
        return self.session.mode

    @property
    def turns(self):
        return self.session.turns

    def status(self) -> ManagedChatStatus:
        return ManagedChatStatus(
            mode=self.session.mode,
            turns=len(self.session.turns),
            exchanges=len(self.session.turns) // 2,
            context_chars=len(self.session.context_text()),
            max_context_chars=self.max_context_chars,
            max_exchanges=self.max_exchanges,
        )

    def clear(self) -> ManagedChatStatus:
        self.session.turns.clear()
        return self.status()

    def undo(self) -> bool:
        if len(self.session.turns) < 2:
            return False
        del self.session.turns[-2:]
        return True

    def set_mode(self, mode: str) -> ManagedChatStatus:
        self.session.set_mode(mode)
        return self.status()

    def _bound_latest_pair(self) -> None:
        if len(self.session.turns) < 2:
            return
        user = self.session.turns[-2]
        assistant = self.session.turns[-1]
        assistant_text = _clip_middle(assistant.text, self.max_stored_assistant_chars)
        self.session.turns[-1] = ChatTurn("assistant", assistant_text)

        while len(self.session.turns) > 2 and len(self.session.context_text()) > self.max_context_chars:
            del self.session.turns[:2]

        if len(self.session.context_text()) <= self.max_context_chars:
            return

        user = self.session.turns[-2]
        assistant = self.session.turns[-1]
        fixed_overhead = len("user: ") + len("\nassistant: ")
        available = max(0, self.max_context_chars - fixed_overhead)
        user_budget = min(len(user.text), available // 2)
        assistant_budget = max(0, available - user_budget)
        self.session.turns[-2] = ChatTurn("user", _clip_middle(user.text, user_budget))
        self.session.turns[-1] = ChatTurn("assistant", _clip_middle(assistant.text, assistant_budget))

    def submit(self, text: str, responder: Callable[[str, str, str], str]) -> str:
        value = str(text).strip()
        if not value:
            raise ValueError("chat input is required")
        if len(value) > self.max_input_chars:
            raise ValueError("chat input exceeds max_input_chars")

        if value == ":clear":
            self.clear()
            return "chat_cleared"
        if value == ":undo":
            return "chat_undo=1" if self.undo() else "chat_undo=0"
        if value == ":status":
            s = self.status()
            return (
                f"mode={s.mode} turns={s.turns} exchanges={s.exchanges} "
                f"context_chars={s.context_chars}/{s.max_context_chars}"
            )
        if value.startswith(":mode "):
            mode = value[6:].strip().lower()
            self.set_mode(mode)
            return f"mode={self.mode}"

        response = self.session.submit(value, responder)
        self._bound_latest_pair()
        return response
