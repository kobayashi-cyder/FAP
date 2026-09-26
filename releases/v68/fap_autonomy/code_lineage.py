from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List


class CodeLineageLedger:
    """Append-only hash-chained provenance for repository coding attempts."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(obj: Dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def append(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        prev = ''
        if self.path.exists() and self.path.stat().st_size:
            last = json.loads(self.path.read_text(encoding='utf-8').splitlines()[-1])
            prev = str(last.get('event_hash', ''))
        body = {'kind': str(kind), 'payload': payload, 'prev_hash': prev}
        rec = dict(body, event_hash=self._hash(body))
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
            f.flush(); os.fsync(f.fileno())
        return rec

    def validate(self) -> bool:
        prev = ''
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding='utf-8').splitlines():
            rec = json.loads(line)
            body = {'kind': rec['kind'], 'payload': rec['payload'], 'prev_hash': rec['prev_hash']}
            if rec['prev_hash'] != prev or rec.get('event_hash') != self._hash(body):
                return False
            prev = rec['event_hash']
        return True
