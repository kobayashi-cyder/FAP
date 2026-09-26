from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ABDecision:
    status: str
    rollback: bool
    baseline_n: int
    active_n: int
    baseline_success: float
    active_success: float
    success_delta: float
    baseline_quality: float
    active_quality: float
    quality_delta: float
    latency_ratio: float


def _p95(values):
    if not values:
        return 0.0
    xs = sorted(float(x) for x in values)
    return xs[max(0, math.ceil(0.95 * len(xs)) - 1)]


class ABObserver:
    def __init__(self, path: str, *, min_per_arm: int = 12, max_success_drop: float = .08,
                 max_quality_drop: float = .08, max_latency_ratio: float = 1.5):
        if min_per_arm < 1:
            raise ValueError('min_per_arm must be >= 1')
        self.path = path
        self.min_per_arm = int(min_per_arm)
        self.max_success_drop = float(max_success_drop)
        self.max_quality_drop = float(max_quality_drop)
        self.max_latency_ratio = float(max_latency_ratio)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as con:
            con.execute('CREATE TABLE IF NOT EXISTS obs(event_id TEXT PRIMARY KEY, capability_id TEXT NOT NULL, candidate_digest TEXT NOT NULL, arm TEXT NOT NULL, verified INT NOT NULL, success INT NOT NULL, quality REAL NOT NULL, latency REAL NOT NULL)')

    def ingest(self, *, event_id, capability_id, candidate_digest, arm, verified, success, quality, latency_ms):
        if not verified:
            return False
        if arm not in {'baseline', 'active'}:
            raise ValueError('invalid arm')
        quality = float(quality); latency_ms = float(latency_ms)
        if not 0.0 <= quality <= 1.0:
            raise ValueError('quality must be in 0..1')
        if latency_ms < 0:
            raise ValueError('latency_ms must be non-negative')
        try:
            with closing(sqlite3.connect(self.path)) as con:
                con.execute('INSERT INTO obs VALUES(?,?,?,?,?,?,?,?)',
                            (str(event_id), str(capability_id), str(candidate_digest), arm, 1,
                             int(bool(success)), quality, latency_ms))
                con.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def decide(self, *, capability_id, candidate_digest):
        with closing(sqlite3.connect(self.path)) as con:
            rows = con.execute('SELECT arm,success,quality,latency FROM obs WHERE capability_id=? AND candidate_digest=?',
                               (capability_id, candidate_digest)).fetchall()
        by = {arm: [r for r in rows if r[0] == arm] for arm in ('baseline', 'active')}
        def stat(rs):
            n = len(rs)
            return (n,
                    sum(r[1] for r in rs) / n if n else 0.0,
                    sum(r[2] for r in rs) / n if n else 0.0,
                    _p95([r[3] for r in rs]))
        bn, bs, bq, bl = stat(by['baseline']); an, active_s, aq, al = stat(by['active'])
        sd = active_s - bs; qd = aq - bq; lr = al / bl if bl > 0 and an else 1.0
        enough = bn >= self.min_per_arm and an >= self.min_per_arm
        rollback = enough and (sd < -self.max_success_drop or qd < -self.max_quality_drop or lr > self.max_latency_ratio)
        return ABDecision('rollback_required' if rollback else ('monitoring' if not enough else 'healthy'),
                          rollback, bn, an, bs, active_s, sd, bq, aq, qd, lr)
