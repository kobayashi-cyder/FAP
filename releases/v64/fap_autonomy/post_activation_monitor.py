from __future__ import annotations

import json
import sqlite3
import statistics
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Optional

from .activation_manager import ActivationManager


class PostActivationMonitor:
    """Verified runtime regression monitor with duplicate-event protection.

    Quality scores must use the same normalized 0..1 verifier scale as the activation
    baseline. Unverified observations are intentionally ignored.
    """

    def __init__(self, path: str, activation: ActivationManager, *, min_samples: int = 12,
                 window: int = 20, max_quality_drop: float = 0.08,
                 min_success_rate: float = 0.80, max_latency_ratio: float = 1.80):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.activation = activation
        self.min_samples = int(min_samples)
        self.window = int(window)
        self.max_quality_drop = float(max_quality_drop)
        self.min_success_rate = float(min_success_rate)
        self.max_latency_ratio = float(max_latency_ratio)
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(self.path, isolation_level=None)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with closing(self._connect()) as con:
            con.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runtime_observations (
                    event_id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    candidate_digest TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    quality REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runtime_cap_digest
                    ON runtime_observations(capability_id, candidate_digest, created_at);
            """)

    def ingest(self, *, event_id: str, capability_id: str, verified: bool,
               success: bool, quality: float, latency_ms: float,
               evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not verified:
            return {"accepted": False, "reason": "unverified"}
        if not (0.0 <= float(quality) <= 1.0) or float(latency_ms) < 0:
            return {"accepted": False, "reason": "invalid_metrics"}
        current = self.activation.current(capability_id)
        if current is None:
            return {"accepted": False, "reason": "no_active_candidate"}
        try:
            with closing(self._connect()) as con:
                con.execute(
                    """INSERT INTO runtime_observations(event_id, capability_id, candidate_digest,
                       success, quality, latency_ms, evidence_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, capability_id, current["candidate_digest"], int(bool(success)),
                     float(quality), float(latency_ms), json.dumps(evidence or {}, ensure_ascii=False, sort_keys=True), time.time()),
                )
        except sqlite3.IntegrityError:
            return {"accepted": False, "reason": "duplicate_event"}
        return {"accepted": True, "candidate_digest": current["candidate_digest"]}

    def evaluate(self, capability_id: str) -> Dict[str, Any]:
        current = self.activation.current(capability_id)
        if current is None:
            return {"status": "no_active_candidate"}
        digest = current["candidate_digest"]
        with closing(self._connect()) as con:
            rows = con.execute(
                """SELECT * FROM runtime_observations WHERE capability_id=? AND candidate_digest=?
                   ORDER BY created_at DESC, event_id DESC LIMIT ?""",
                (capability_id, digest, self.window),
            ).fetchall()
        rows = list(reversed(rows))
        if len(rows) < self.min_samples:
            return {"status": "insufficient_evidence", "samples": len(rows), "required": self.min_samples}

        success_rate = sum(int(r["success"]) for r in rows) / len(rows)
        mean_quality = statistics.fmean(float(r["quality"]) for r in rows)
        latencies = sorted(float(r["latency_ms"]) for r in rows)
        p95_index = min(len(latencies) - 1, max(0, int(round(0.95 * len(latencies) + 0.5)) - 1))
        p95_latency = latencies[p95_index]
        baseline_quality = current.get("baseline_quality")
        baseline_latency = current.get("baseline_latency_ms")

        reasons = []
        if baseline_quality is not None and mean_quality < float(baseline_quality) - self.max_quality_drop:
            reasons.append("quality_regression")
        if success_rate < self.min_success_rate:
            reasons.append("success_rate_regression")
        if baseline_latency not in (None, 0) and p95_latency > float(baseline_latency) * self.max_latency_ratio:
            reasons.append("latency_regression")

        metrics = {
            "samples": len(rows), "success_rate": success_rate, "mean_quality": mean_quality,
            "p95_latency_ms": p95_latency, "baseline_quality": baseline_quality,
            "baseline_latency_ms": baseline_latency, "reasons": reasons,
        }
        if not reasons:
            return {"status": "healthy", **metrics}
        rollback = self.activation.rollback(capability_id, reason="post_activation_regression", evidence=metrics)
        return {"status": "rollback_triggered" if rollback.get("rolled_back") else "regression_detected_no_rollback",
                **metrics, "rollback": rollback}
