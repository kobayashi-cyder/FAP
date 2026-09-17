from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PromotionState:
    capability_id: str
    candidate_digest: str
    state: str
    verified_trials: int
    verified_successes: int
    verified_failures: int
    success_rate: float
    mean_confidence: float
    latest_dev_score: float
    latest_holdout_score: float
    latest_regression_delta: float
    resource_ok: bool


class PromotionLedger:
    """Persistent, replay-resistant lifecycle ledger for candidate evaluations.

    A trial_id is unique. Replaying the same evaluation cannot increase promotion counts.
    Lifecycle is keyed by candidate digest, so changing candidate bytes starts a fresh record.
    """

    def __init__(self, path: str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(self.path, isolation_level=None)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with closing(self._connect()) as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS promotion_trials (
                    trial_id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    candidate_digest TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    dev_score REAL NOT NULL,
                    holdout_score REAL NOT NULL,
                    regression_delta REAL NOT NULL,
                    resource_ok INTEGER NOT NULL,
                    holdout_hash TEXT NOT NULL,
                    evidence_key TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(capability_id, candidate_digest, evidence_key)
                );
                CREATE INDEX IF NOT EXISTS idx_promotion_candidate
                    ON promotion_trials(capability_id, candidate_digest, created_at);
                """
            )

    def record_trial(self, *, trial_id: str, capability_id: str, candidate_digest: str,
                     success: bool, confidence: float, dev_score: float,
                     holdout_score: float, regression_delta: float, resource_ok: bool,
                     holdout_hash: str, evidence_key: str, evidence: Dict[str, Any]) -> bool:
        try:
            with closing(self._connect()) as con:
                con.execute(
                    """
                    INSERT INTO promotion_trials(
                        trial_id, capability_id, candidate_digest, success, confidence,
                        dev_score, holdout_score, regression_delta, resource_ok,
                        holdout_hash, evidence_key, evidence_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trial_id, capability_id, candidate_digest, int(bool(success)),
                        float(confidence), float(dev_score), float(holdout_score),
                        float(regression_delta), int(bool(resource_ok)), holdout_hash, evidence_key,
                        json.dumps(evidence, ensure_ascii=False, sort_keys=True), time.time(),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def state(self, capability_id: str, candidate_digest: str, *, max_regression: float = 0.02) -> PromotionState:
        with closing(self._connect()) as con:
            rows = con.execute(
                """SELECT * FROM promotion_trials
                   WHERE capability_id=? AND candidate_digest=? ORDER BY created_at, trial_id""",
                (capability_id, candidate_digest),
            ).fetchall()
        n = len(rows)
        successes = sum(int(r["success"]) for r in rows)
        failures = n - successes
        rate = successes / n if n else 0.0
        mean_conf = sum(float(r["confidence"]) for r in rows) / n if n else 0.0
        latest = rows[-1] if rows else None
        resource_ok = bool(latest["resource_ok"]) if latest else False
        dev = float(latest["dev_score"]) if latest else 0.0
        holdout = float(latest["holdout_score"]) if latest else 0.0
        regression = float(latest["regression_delta"]) if latest else 0.0

        state = "ephemeral"
        if failures >= 3 and rate < 0.5:
            state = "rejected"
        else:
            eligible = resource_ok and regression >= -max_regression and holdout > 0.0
            if eligible and n >= 2 and rate >= 0.5:
                state = "shadow"
            if eligible and n >= 5 and rate >= 0.8 and mean_conf >= 0.68 and holdout >= dev * 0.85:
                state = "consolidated"
        return PromotionState(
            capability_id=capability_id,
            candidate_digest=candidate_digest,
            state=state,
            verified_trials=n,
            verified_successes=successes,
            verified_failures=failures,
            success_rate=rate,
            mean_confidence=mean_conf,
            latest_dev_score=dev,
            latest_holdout_score=holdout,
            latest_regression_delta=regression,
            resource_ok=resource_ok,
        )

    def trials(self, capability_id: str, candidate_digest: str) -> List[Dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                """SELECT * FROM promotion_trials WHERE capability_id=? AND candidate_digest=?
                   ORDER BY created_at, trial_id""",
                (capability_id, candidate_digest),
            ).fetchall()
        return [dict(r) for r in rows]


def digest_tree(path: str) -> str:
    root = Path(path)
    h = hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file() and "__pycache__" not in x.parts):
        rel = p.relative_to(root).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        data = p.read_bytes()
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()
