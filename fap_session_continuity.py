from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
from math import isfinite
import re
from threading import RLock
from typing import Any, Mapping, Sequence

from fap_exponential_linear import (
    ExponentialLinearPolicy,
    InteractionBudget,
    budget_for_demand,
    estimate_interaction_demand,
)


_ALLOWED_ROLES = frozenset({"user", "assistant", "system", "tool"})
_SAFE_ID = re.compile(r"^[0-9A-Za-z_.:-]{1,128}$")


def _coerce_history_rows(value: object) -> tuple[Any, ...]:
    """Fail closed on malformed history containers instead of raising in chat."""
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, (str, bytes, bytearray)):
        return ()
    try:
        return tuple(value)
    except (TypeError, ValueError, OverflowError):
        return ()


def _safe_pressure_hint(value: object) -> float:
    """Normalize caller pressure to a finite bounded hint for demand estimation."""
    try:
        hint = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not isfinite(hint):
        return 0.0
    return min(1.0, max(0.0, hint))


def _coerce_route_tags(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (bytes, bytearray)):
        return ()
    try:
        return tuple(value)
    except (TypeError, ValueError, OverflowError):
        return ()


@dataclass(frozen=True)
class AdaptiveContextSelection:
    history: tuple[dict[str, Any], ...]
    budget: InteractionBudget
    source_turns: int
    selected_turns: int
    selected_chars: int
    dropped_turns: int

    def to_dict(self) -> dict:
        return {
            "budget": self.budget.to_dict(),
            "source_turns": self.source_turns,
            "selected_turns": self.selected_turns,
            "selected_chars": self.selected_chars,
            "dropped_turns": self.dropped_turns,
        }


class AdaptiveContextSelector:
    """Select bounded recent context according to the exponential-linear budget."""

    def __init__(
        self,
        *,
        policy: ExponentialLinearPolicy | None = None,
        max_turns: int = 128,
        max_turn_chars: int = 20_000,
        hard_context_chars: int = 250_000,
    ) -> None:
        if not 1 <= int(max_turns) <= 512:
            raise ValueError("max_turns must be in [1, 512]")
        if not 256 <= int(max_turn_chars) <= 100_000:
            raise ValueError("max_turn_chars must be in [256, 100000]")
        if not 1_000 <= int(hard_context_chars) <= 1_000_000:
            raise ValueError("hard_context_chars must be in [1000, 1000000]")
        self.policy = policy or ExponentialLinearPolicy()
        self.max_turns = int(max_turns)
        self.max_turn_chars = int(max_turn_chars)
        self.hard_context_chars = int(hard_context_chars)

    def select(
        self,
        text: str,
        history: Sequence[Mapping[str, Any]],
        *,
        pressure_hint: float = 0.0,
    ) -> AdaptiveContextSelection:
        rows = _coerce_history_rows(history)
        demand = estimate_interaction_demand(
            text,
            history_turns=len(rows),
            pressure_hint=_safe_pressure_hint(pressure_hint),
        )
        budget = budget_for_demand(demand, policy=self.policy)
        char_limit = min(self.hard_context_chars, budget.context_chars)
        turn_limit = min(
            self.max_turns,
            max(4, budget.reasoning_steps * 2),
        )

        chosen_rev: list[dict[str, Any]] = []
        used_chars = 0
        for raw in reversed(rows):
            if len(chosen_rev) >= turn_limit:
                break
            row = self._normalize_row(raw)
            if row is None:
                continue
            available = char_limit - used_chars
            if available <= 0:
                break
            text_value = row["text"]
            if len(text_value) > available:
                if not chosen_rev:
                    text_value = text_value[-available:]
                    row["text"] = text_value
                else:
                    break
            chosen_rev.append(row)
            used_chars += len(text_value)

        selected = tuple(reversed(chosen_rev))
        return AdaptiveContextSelection(
            history=selected,
            budget=budget,
            source_turns=len(rows),
            selected_turns=len(selected),
            selected_chars=used_chars,
            dropped_turns=max(0, len(rows) - len(selected)),
        )

    def _normalize_row(
        self,
        raw: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None
        role = str(raw.get("role") or "").strip().lower()
        if role not in _ALLOWED_ROLES:
            return None
        text = raw.get("text")
        if not isinstance(text, str):
            content = raw.get("content")
            text = content if isinstance(content, str) else ""
        text = text.strip()
        if not text:
            return None
        if len(text) > self.max_turn_chars:
            text = text[-self.max_turn_chars :]

        out: dict[str, Any] = {"role": role, "text": text}
        meta = raw.get("meta")
        if isinstance(meta, Mapping):
            safe_meta: dict[str, Any] = {}
            for key in ("intent", "verdict", "ability"):
                value = meta.get(key)
                if isinstance(value, float) and not isfinite(value):
                    continue
                if isinstance(value, (str, int, float, bool)) and len(str(value)) <= 160:
                    safe_meta[key] = value
            if safe_meta:
                out["meta"] = safe_meta
        return out


@dataclass(frozen=True)
class RouteContinuityEvent:
    endpoint_id: str
    state: str
    route_tags: tuple[str, ...]


@dataclass(frozen=True)
class RouteContinuitySnapshot:
    session_id: str
    events: tuple[RouteContinuityEvent, ...]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "events": [asdict(event) for event in self.events],
        }


class SessionRouteLedger:
    """Small in-memory endpoint-history ledger. It stores no message text."""

    def __init__(
        self,
        *,
        max_sessions: int = 128,
        max_events_per_session: int = 32,
    ) -> None:
        if not 1 <= int(max_sessions) <= 4096:
            raise ValueError("max_sessions must be in [1, 4096]")
        if not 1 <= int(max_events_per_session) <= 256:
            raise ValueError("max_events_per_session must be in [1, 256]")
        self.max_sessions = int(max_sessions)
        self.max_events_per_session = int(max_events_per_session)
        self._rows: OrderedDict[str, list[RouteContinuityEvent]] = OrderedDict()
        self._lock = RLock()

    def record(
        self,
        session_id: str,
        endpoint_id: str,
        *,
        state: str = "handled",
        route_tags: Sequence[str] = (),
    ) -> None:
        sid = self._safe_id(session_id, 80, "session_id")
        endpoint = self._safe_id(endpoint_id, 128, "endpoint_id")
        state_value = self._safe_id(state, 64, "state")
        tags = tuple(
            str(tag).strip()
            for tag in _coerce_route_tags(route_tags)
            if (
                isinstance(tag, str)
                and _SAFE_ID.fullmatch(str(tag).strip())
            )
        )[:32]

        with self._lock:
            rows = self._rows.pop(sid, [])
            rows.append(
                RouteContinuityEvent(
                    endpoint_id=endpoint,
                    state=state_value,
                    route_tags=tags,
                )
            )
            self._rows[sid] = rows[-self.max_events_per_session :]
            while len(self._rows) > self.max_sessions:
                self._rows.popitem(last=False)

    def snapshot(self, session_id: str) -> RouteContinuitySnapshot:
        sid = self._safe_id(session_id, 80, "session_id")
        with self._lock:
            if sid not in self._rows:
                return RouteContinuitySnapshot(sid, ())
            rows = self._rows.pop(sid)
            self._rows[sid] = rows
            return RouteContinuitySnapshot(sid, tuple(rows))

    def clear(self, session_id: str) -> None:
        sid = self._safe_id(session_id, 80, "session_id")
        with self._lock:
            self._rows.pop(sid, None)

    @staticmethod
    def _safe_id(value: str, limit: int, name: str) -> str:
        text = str(value or "").strip()
        if not text or len(text) > limit:
            raise ValueError(f"{name} is empty or oversized")
        if not _SAFE_ID.fullmatch(text):
            raise ValueError(f"{name} contains unsupported characters")
        return text
