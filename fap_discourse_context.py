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
