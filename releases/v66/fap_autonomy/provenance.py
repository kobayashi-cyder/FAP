from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _canonical(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ProvenanceLedger:
    """Append-only hash-chained provenance ledger.

    This is tamper-evident bookkeeping, not a cryptographic signature system.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def append(self, event_type: str, *, capability_id: str = "",
               candidate_digest: str = "", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        integrity = self.verify()
        if not integrity.get("valid"):
            raise ValueError("provenance ledger integrity failure")
        existing = self.entries()
        prev_hash = existing[-1]["hash"] if existing else "0" * 64
        record = {
            "seq": len(existing) + 1,
            "ts": time.time(),
            "event_type": str(event_type),
            "capability_id": str(capability_id),
            "candidate_digest": str(candidate_digest),
            "payload": payload or {},
            "prev_hash": prev_hash,
        }
        record["hash"] = hashlib.sha256(_canonical(record)).hexdigest()
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record

    def verify(self) -> Dict[str, Any]:
        try:
            entries = self.entries()
        except Exception as exc:
            return {"valid": False, "entries": 0, "error": f"parse_error:{exc}"}
        prev_hash = "0" * 64
        for i, record in enumerate(entries, start=1):
            if record.get("seq") != i:
                return {"valid": False, "entries": len(entries), "error": "sequence_mismatch", "at": i}
            if record.get("prev_hash") != prev_hash:
                return {"valid": False, "entries": len(entries), "error": "chain_mismatch", "at": i}
            claimed = record.get("hash")
            body = dict(record)
            body.pop("hash", None)
            actual = hashlib.sha256(_canonical(body)).hexdigest()
            if claimed != actual:
                return {"valid": False, "entries": len(entries), "error": "hash_mismatch", "at": i}
            prev_hash = claimed
        return {"valid": True, "entries": len(entries), "head_hash": prev_hash}
