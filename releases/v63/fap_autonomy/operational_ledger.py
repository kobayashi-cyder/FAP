from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import closing
from typing import Dict, Iterable, List, Tuple

from .models import BenchmarkCase, BenchmarkResult
from .v59_bridge import V59OutcomeAdapter


SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_events (
  turn_id TEXT PRIMARY KEY,
  bucket TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verified_events_bucket ON verified_events(bucket);
"""


class OperationalLedger:
    """Small idempotent SQLite ledger for verified V59 outcomes."""

    def __init__(self, path: str, audit_fraction: float = 0.20, salt: str = "fap-v61"):
        if not (0.0 <= audit_fraction < 1.0):
            raise ValueError("audit_fraction must be in [0, 1)")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_fraction = audit_fraction
        self.salt = salt
        with closing(self._connect()) as cx:
            cx.executescript(SCHEMA)

    def _connect(self):
        return sqlite3.connect(str(self.path), isolation_level=None)

    def _bucket(self, turn_id: str) -> str:
        digest = hashlib.sha256((self.salt + "\0" + turn_id).encode("utf-8")).digest()
        u = int.from_bytes(digest[:8], "big") / float(2**64)
        return "audit" if u < self.audit_fraction else "diagnostic"

    @staticmethod
    def _result_to_payload(r: BenchmarkResult) -> Dict:
        return {"id": r.case.case_id, "domain": r.case.domain, "task": r.case.task,
                "expected": r.case.expected, "case_metadata": r.case.metadata,
                "success": r.success, "actual": r.actual, "error": r.error,
                "latency_ms": r.latency_ms, "teacher_used": r.teacher_used,
                "verified": r.verified, "verifier_confidence": r.verifier_confidence,
                "metadata": r.metadata}

    @staticmethod
    def _payload_to_result(p: Dict) -> BenchmarkResult:
        case = BenchmarkCase(case_id=str(p["id"]), domain=str(p.get("domain", "unknown")),
                             task=str(p.get("task", "")), expected=p.get("expected"),
                             metadata=dict(p.get("case_metadata", {})))
        return BenchmarkResult(case=case, success=bool(p.get("success", False)), actual=p.get("actual"),
                               error=str(p.get("error", "")), latency_ms=float(p.get("latency_ms", 0.0) or 0.0),
                               teacher_used=bool(p.get("teacher_used", False)), verified=bool(p.get("verified", False)),
                               verifier_confidence=float(p.get("verifier_confidence", 0.0) or 0.0),
                               metadata=dict(p.get("metadata", {})))

    def ingest_rows(self, rows: Iterable[Dict]) -> Dict[str, int]:
        verified = V59OutcomeAdapter.verified_results(rows)
        inserted = duplicate = 0
        with closing(self._connect()) as cx:
            for r in verified:
                payload = json.dumps(self._result_to_payload(r), ensure_ascii=False, separators=(",", ":"))
                cur = cx.execute("INSERT OR IGNORE INTO verified_events(turn_id,bucket,payload_json) VALUES(?,?,?)",
                                 (r.case.case_id, self._bucket(r.case.case_id), payload))
                if cur.rowcount:
                    inserted += 1
                else:
                    duplicate += 1
        return {"verified_input": len(verified), "inserted": inserted, "duplicates": duplicate}

    def results(self, bucket: str = "diagnostic") -> List[BenchmarkResult]:
        if bucket not in {"diagnostic", "audit", "all"}:
            raise ValueError("bucket must be diagnostic, audit or all")
        query = "SELECT payload_json FROM verified_events"
        args: Tuple = ()
        if bucket != "all":
            query += " WHERE bucket=?"
            args = (bucket,)
        query += " ORDER BY turn_id"
        with closing(self._connect()) as cx:
            rows = [json.loads(x[0]) for x in cx.execute(query, args)]
        return [self._payload_to_result(p) for p in rows]

    def counts(self) -> Dict[str, int]:
        with closing(self._connect()) as cx:
            counts = {"diagnostic": 0, "audit": 0}
            for bucket, n in cx.execute("SELECT bucket, COUNT(*) FROM verified_events GROUP BY bucket"):
                counts[bucket] = int(n)
        counts["all"] = counts["diagnostic"] + counts["audit"]
        return counts
