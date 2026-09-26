from __future__ import annotations

import json
import math
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Dict

from .telemetry_v66 import AttestedRuntimeTelemetry


def _p95(values):
    xs = sorted(float(x) for x in values)
    return xs[max(0, math.ceil(.95 * len(xs)) - 1)] if xs else 0.0


class ProductionCapabilityMatrix:
    """Operational evidence matrix; this is not a public benchmark score."""

    def __init__(self, path: str):
        self.path = str(path); Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence(
                    event_id TEXT PRIMARY KEY, capability_id TEXT NOT NULL, candidate_digest TEXT NOT NULL,
                    stage_ratio REAL NOT NULL, success INT NOT NULL, quality REAL NOT NULL, latency REAL NOT NULL,
                    attestation_id TEXT NOT NULL UNIQUE, wrapper_id TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS control_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, capability_id TEXT NOT NULL,
                    candidate_digest TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at REAL NOT NULL
                );
                """
            )

    def ingest(self, event: AttestedRuntimeTelemetry) -> bool:
        if not event.verified or not event.attestation_verified or not event.production:
            raise ValueError("matrix accepts only verified attested production evidence")
        try:
            with closing(sqlite3.connect(self.path)) as con:
                con.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (event.event_id, event.capability_id, event.candidate_digest, event.stage_ratio,
                             int(event.success), event.quality, event.latency_ms, event.attestation_id,
                             event.wrapper_id, time.time()))
                con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def record_control(self, *, capability_id: str, candidate_digest: str, kind: str, payload: Dict[str, object]) -> None:
        with closing(sqlite3.connect(self.path)) as con:
            con.execute("INSERT INTO control_events(capability_id,candidate_digest,kind,payload_json,created_at) VALUES(?,?,?,?,?)",
                        (capability_id, candidate_digest, kind, json.dumps(payload, sort_keys=True), time.time()))
            con.commit()

    def snapshot(self, capability_id: str) -> Dict[str, object]:
        with closing(sqlite3.connect(self.path)) as con:
            rows = con.execute("SELECT candidate_digest,stage_ratio,success,quality,latency FROM evidence WHERE capability_id=?",
                               (capability_id,)).fetchall()
            ctrl = con.execute("SELECT kind,COUNT(*) FROM control_events WHERE capability_id=? GROUP BY kind",
                               (capability_id,)).fetchall()
        n = len(rows)
        stages: Dict[str, int] = {}
        for r in rows: stages[f"{float(r[1]):.2f}"] = stages.get(f"{float(r[1]):.2f}", 0) + 1
        return {
            "capability_id": capability_id, "evidence_kind": "verified_attested_production",
            "public_benchmark": False, "n": n,
            "success_rate": (sum(int(r[2]) for r in rows) / n if n else 0.0),
            "mean_quality": (sum(float(r[3]) for r in rows) / n if n else 0.0),
            "p95_latency_ms": _p95([r[4] for r in rows]),
            "candidate_count": len({r[0] for r in rows}), "stage_counts": stages,
            "control_events": {str(k): int(v) for k, v in ctrl},
        }
