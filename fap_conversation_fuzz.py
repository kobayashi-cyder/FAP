from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import unicodedata
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ConversationFuzzCase:
    index: int
    text: str
    history: Any
    channel: Any
    pressure_hint: Any


def _knowledge_aliases(root: Path) -> tuple[str, ...]:
    aliases: list[str] = []
    folder = Path(root) / "knowledge"
    if folder.exists():
        for path in sorted(folder.rglob("*.jsonl")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, Mapping):
                    continue
                for key in ("subject_aliases", "action_aliases", "aliases"):
                    values = row.get(key)
                    if not isinstance(values, list):
                        continue
                    for value in values:
                        if isinstance(value, str) and value.strip():
                            aliases.append(value.strip())
    return tuple(dict.fromkeys(aliases))


def _random_char(rng: random.Random) -> str:
    mode = rng.randrange(8)
    if mode == 0:
        return chr(rng.randint(0x21, 0x7E))
    if mode == 1:
        return chr(rng.randint(0x3041, 0x3096))
    if mode == 2:
        return chr(rng.randint(0x30A1, 0x30FA))
    if mode == 3:
        return chr(rng.randint(0x4E00, 0x9FFF))
    if mode == 4:
        return chr(rng.randint(0x1F600, 0x1F64F))
    if mode == 5:
        return chr(rng.randint(0x0300, 0x036F))
    if mode == 6:
        return rng.choice((" ", "\t", "\n", "\r", "\u3000"))
    return rng.choice(("、", "。", "!", "?", ":", ";", "-", "_", "・", "\u0000"))


def _random_text(rng: random.Random, minimum: int = 0, maximum: int = 160) -> str:
    if maximum < minimum:
        maximum = minimum
    size = rng.randint(minimum, maximum)
    return "".join(_random_char(rng) for _ in range(size))


def _semantic_text(rng: random.Random, aliases: tuple[str, ...], index: int) -> str:
    mode = index % 6
    if aliases and mode in (0, 1, 2):
        count = 1 if mode == 0 else min(len(aliases), 2 + (index % 2))
        picked = [rng.choice(aliases) for _ in range(count)]
        if mode == 1:
            picked = [unicodedata.normalize("NFKC", value) for value in picked]
        separators = (" ", "　", "、", "。", "?", "!", "\n", "-", "_", "・")
        return rng.choice(separators).join(picked) + _random_text(rng, 0, 24)
    if mode == 3:
        return _random_text(rng, 0, 256)
    if mode == 4:
        return _random_text(rng, 1024, 4096)
    return rng.choice(("", " ", "\t", "\n", "　")) + _random_text(rng, 0, 12)


def _history_row(rng: random.Random, index: int) -> dict[str, Any]:
    role = rng.choice(("user", "assistant", "system", "tool", "invalid", ""))
    meta_values: tuple[Any, ...] = (
        "chat",
        "OK",
        True,
        rng.randint(-100, 100),
        rng.random(),
        float("nan"),
        float("inf"),
        float("-inf"),
        {"nested": "ignored"},
    )
    return {
        "role": role,
        "text": _random_text(rng, 0, 320),
        "content": _random_text(rng, 0, 160),
        "meta": {
            "intent": rng.choice(meta_values),
            "verdict": rng.choice(meta_values),
            "ability": rng.choice(meta_values),
            "untrusted": _random_text(rng, 0, 64),
        },
        "extra": {"index": index},
    }


def _history(rng: random.Random, index: int) -> Any:
    mode = index % 7
    rows = [_history_row(rng, index * 10 + i) for i in range(rng.randint(0, 8))]
    if mode == 0:
        return tuple(rows)
    if mode == 1:
        mixed: list[Any] = list(rows)
        mixed.extend((None, 7, "not-a-row", ["nested"]))
        rng.shuffle(mixed)
        return mixed
    if mode == 2:
        return None
    if mode == 3:
        return rng.randint(-1000, 1000)
    if mode == 4:
        return _random_text(rng, 0, 80)
    if mode == 5:
        return _history_row(rng, index)
    return rows


def _pressure_hint(rng: random.Random, index: int) -> Any:
    mode = index % 9
    if mode == 0:
        return rng.random()
    if mode == 1:
        return float("nan")
    if mode == 2:
        return float("inf")
    if mode == 3:
        return float("-inf")
    if mode == 4:
        return "invalid-pressure"
    if mode == 5:
        return None
    if mode == 6:
        return -rng.random() * 10.0
    if mode == 7:
        return 1.0 + rng.random() * 10.0
    return rng.randint(-10, 10)


def _channel(rng: random.Random, index: int) -> Any:
    mode = index % 5
    if mode == 0:
        return "chat"
    if mode == 1:
        return ""
    if mode == 2:
        return _random_text(rng, 1, 32)
    if mode == 3:
        return _random_text(rng, 65, 96)
    return None


def generate_conversation_corpus(
    root: Path,
    *,
    seed: int,
    count: int = 1024,
) -> Iterable[ConversationFuzzCase]:
    if count < 1:
        return ()
    rng = random.Random(int(seed))
    aliases = _knowledge_aliases(Path(root))
    cases: list[ConversationFuzzCase] = []
    for index in range(int(count)):
        cases.append(
            ConversationFuzzCase(
                index=index,
                text=_semantic_text(rng, aliases, index),
                history=_history(rng, index),
                channel=_channel(rng, index),
                pressure_hint=_pressure_hint(rng, index),
            )
        )
    return tuple(cases)


def is_nonfinite_number(value: Any) -> bool:
    return isinstance(value, float) and not math.isfinite(value)
