from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from math import sqrt


@dataclass(frozen=True)
class MemoryItem:
    key: str
    text: str
    signature: tuple[float, ...]
    utility: float = 0.0
    confidence: float = 0.5
    accesses: int = 0
    contradiction_group: str | None = None


def _signature(text: str, channels: int) -> tuple[float, ...]:
    """Dependency-free stable hashed bag-of-tokens signature."""
    out = [0.0] * channels
    for token in text.lower().split():
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % channels
        sign = 1.0 if digest[4] & 1 else -1.0
        out[index] += sign
    return tuple(out)


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class BoundedHotColdMemory:
    """FCA-derived bounded memory for long-running FAP goals.

    The memory is deliberately separate from planner/critic state. Callers choose
    what to remember and what retrieved excerpts to expose to the planner.
    """

    def __init__(self, *, channels: int = 128, hot_capacity: int = 64,
                 cold_capacity: int = 4096, page_in: int = 8) -> None:
        if channels < 8:
            raise ValueError("channels must be at least 8")
        if min(hot_capacity, cold_capacity, page_in) < 1:
            raise ValueError("capacities must be positive")
        if page_in > hot_capacity:
            raise ValueError("page_in cannot exceed hot_capacity")
        self.channels = int(channels)
        self.hot_capacity = int(hot_capacity)
        self.cold_capacity = int(cold_capacity)
        self.page_in = int(page_in)
        self.hot: dict[str, MemoryItem] = {}
        self.cold: dict[str, MemoryItem] = {}

    def remember(self, key: str, text: str, *, utility: float = 0.0,
                 confidence: float = 0.5,
                 contradiction_group: str | None = None) -> None:
        key, text = key.strip(), text.strip()
        if not key or not text:
            raise ValueError("key and text must be non-empty")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        self.hot[key] = MemoryItem(
            key=key, text=text, signature=_signature(text, self.channels),
            utility=float(utility), confidence=float(confidence),
            contradiction_group=contradiction_group,
        )
        self.cold.pop(key, None)
        self._trim_hot()

    def retrieve(self, query: str, limit: int | None = None) -> tuple[MemoryItem, ...]:
        query = query.strip()
        if not query:
            return ()
        limit = self.page_in if limit is None else max(1, min(int(limit), self.page_in))
        qsig = _signature(query, self.channels)
        candidates = {**self.cold, **self.hot}

        def score(item: MemoryItem) -> tuple[float, float, int, str]:
            return (_cosine(qsig, item.signature) + 0.10 * item.utility
                    + 0.05 * item.confidence, item.utility, item.accesses, item.key)

        ranked = sorted(candidates.values(), key=score, reverse=True)[:limit]
        result = []
        for item in ranked:
            updated = replace(item, accesses=item.accesses + 1)
            self.hot[item.key] = updated
            self.cold.pop(item.key, None)
            result.append(updated)
        self._trim_hot()
        return tuple(result)

    @staticmethod
    def _protected(item: MemoryItem) -> bool:
        return item.contradiction_group is not None or item.confidence >= 0.90

    def _retention(self, item: MemoryItem) -> tuple[int, float, float, int]:
        return (1 if self._protected(item) else 0, item.utility,
                item.confidence, item.accesses)

    def _trim_hot(self) -> None:
        while len(self.hot) > self.hot_capacity:
            victim = min(self.hot.values(), key=self._retention)
            self.cold[victim.key] = victim
            del self.hot[victim.key]
        while len(self.cold) > self.cold_capacity:
            unprotected = [x for x in self.cold.values() if not self._protected(x)]
            victim = min(unprotected or list(self.cold.values()), key=self._retention)
            del self.cold[victim.key]

    @property
    def size(self) -> int:
        return len(self.hot) + len(self.cold)
