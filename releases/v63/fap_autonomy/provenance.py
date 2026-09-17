from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List


class PatchHistory:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, payload: Dict[str, Any]) -> None:
        rec = {"ts": time.time(), "kind": str(kind), "payload": payload}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush(); os.fsync(f.fileno())

    def read_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip(): out.append(json.loads(line))
        return out
