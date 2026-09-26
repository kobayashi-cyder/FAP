from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class HoldoutSeal:
    """Records hashes of evaluator-owned holdout files and verifies immutability."""

    def __init__(self, paths: Iterable[str]):
        self.paths = tuple(str(Path(p).resolve()) for p in paths)
        if not self.paths:
            raise ValueError("at least one holdout path is required")
        self.before = self.snapshot()

    def snapshot(self) -> Dict[str, str]:
        out = {}
        for p in self.paths:
            if not Path(p).is_file():
                raise FileNotFoundError(p)
            out[p] = sha256_file(p)
        return out

    def verify(self) -> Dict[str, object]:
        after = self.snapshot()
        changed = [p for p in self.paths if after[p] != self.before[p]]
        combined = hashlib.sha256(
            "\n".join(sorted(self.before.values())).encode("utf-8")
        ).hexdigest()
        return {"intact": not changed, "changed": changed, "hash": combined, "before": self.before, "after": after}
