from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


def _compact(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[\s\-‐-–—_/／\\|｜・･、。，．,:：;；!?！？'\"「」『』()（）\[\]{}]+", "", value)


@lru_cache(maxsize=8)
def _transparent_aliases(root_text: str) -> tuple[str, ...]:
    root = Path(root_text)
    aliases: list[str] = []
    folder = root / "knowledge"
    if not folder.exists():
        return ()
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
            if not isinstance(row, dict):
                continue
            if str(row.get("kind") or "") != "conversation_discourse":
                continue
            if not bool(row.get("transparent")):
                continue
            for alias in row.get("aliases") or ():
                token = _compact(str(alias))
                if token:
                    aliases.append(token)
    return tuple(dict.fromkeys(aliases))


def is_transparent_discourse_turn(text: str, root: Path | None = None) -> bool:
    token = _compact(text)
    if not token:
        return True
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    return token in _transparent_aliases(str(base.resolve()))


_CORRECTION_BOUNDARY = re.compile(
    r"(?:ではなく(?:て)?|じゃなくて|じゃなく|でなくて|でなく)(?:[、,\s]*)",
    re.I,
)


def focus_explicit_correction(text: str) -> str:
    """Return the asserted side of an explicit A-not-B correction.

    This is grammar-level discourse handling, not a topic list. When a user
    explicitly rejects a prior candidate and supplies a replacement after a
    correction boundary, semantic matching should rank the replacement clause
    rather than rewarding both sides by token length.
    """
    value = unicodedata.normalize("NFKC", str(text or "")).strip()
    if not value:
        return ""
    parts = _CORRECTION_BOUNDARY.split(value, maxsplit=1)
    if len(parts) != 2:
        return value
    asserted = parts[1].strip(" 、,。．!?！？")
    return asserted or value
