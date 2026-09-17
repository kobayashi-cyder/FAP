from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MonitorDecision:
    status: str
    rollback: bool
    verified_cases: int
    success_rate: float
    baseline_success_rate: float
    success_delta: float
    mean_latency_ms: float
    baseline_latency_ms: float
    latency_ratio: float
    reasons: tuple[str, ...]


class PostActivationMonitor:
    """Verified-outcome regression monitor with sample-size gate."""

    def __init__(self, db_path: str, *, min_cases: int = 12, max_success_drop: float = 0.08,
                 max_latency_ratio: float = 1.50):
        self.db_path = str(db_path)
        self.min_cases = int(min_cases)
        self.max_success_drop = float(max_success_drop)
        self.max_latency_ratio = float(max_latency_ratio)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS activation_outcomes(
              event_id TEXT PRIMARY KEY,
              candidate_digest TEXT NOT NULL,
              verified INTEGER NOT NULL,
              success INTEGER NOT NULL,
              latency_ms REAL NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activation_digest ON activation_outcomes(candidate_digest, created_at);
            """)

    def ingest(self, *, event_id: str, candidate_digest: str, verified: bool, success: bool, latency_ms: float) -> bool:
        if not verified:
            return False
        try:
            with closing(sqlite3.connect(self.db_path)) as con:
                con.execute("INSERT INTO activation_outcomes VALUES(?,?,?,?,?,?)",
                            (event_id, candidate_digest, 1, int(bool(success)), float(latency_ms), time.time()))
                con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def evaluate(self, *, candidate_digest: str, baseline_success_rate: float, baseline_latency_ms: float) -> MonitorDecision:
        with closing(sqlite3.connect(self.db_path)) as con:
            rows = con.execute("SELECT success, latency_ms FROM activation_outcomes WHERE candidate_digest=?", (candidate_digest,)).fetchall()
        n = len(rows)
        rate = sum(r[0] for r in rows) / n if n else 0.0
        mean_latency = sum(r[1] for r in rows) / n if n else 0.0
        delta = rate - float(baseline_success_rate)
        latency_ratio = mean_latency / float(baseline_latency_ms) if baseline_latency_ms > 0 and n else 1.0
        reasons = []
        if n >= self.min_cases:
            if delta < -self.max_success_drop:
                reasons.append("success_rate_regression")
            if latency_ratio > self.max_latency_ratio:
                reasons.append("latency_regression")
        return MonitorDecision(
            status="rollback_required" if reasons else ("monitoring" if n < self.min_cases else "healthy"),
            rollback=bool(reasons), verified_cases=n, success_rate=rate,
            baseline_success_rate=float(baseline_success_rate), success_delta=delta,
            mean_latency_ms=mean_latency, baseline_latency_ms=float(baseline_latency_ms),
            latency_ratio=latency_ratio, reasons=tuple(reasons),
        )
