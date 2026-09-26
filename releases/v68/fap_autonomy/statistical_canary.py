from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from statistics import NormalDist
from typing import Dict, Iterable, Sequence

from .canary_controller import StagedCanaryController, _p95


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _sample_var(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def _mean_diff_bounds(baseline: Sequence[float], active: Sequence[float], z: float) -> tuple[float, float, float]:
    """Bounds for baseline-active difference."""
    d = _mean(baseline) - _mean(active)
    se = math.sqrt((_sample_var(baseline) / len(baseline) if baseline else 0.0) +
                   (_sample_var(active) / len(active) if active else 0.0))
    return d, d - z * se, d + z * se


def _success_drop_bounds(b_success: int, bn: int, a_success: int, an: int, z: float) -> tuple[float, float, float]:
    # Agresti-Caffo style smoothing prevents zero-width intervals at 0% or 100%.
    pb = (b_success + 1.0) / (bn + 2.0)
    pa = (a_success + 1.0) / (an + 2.0)
    d = pb - pa
    se = math.sqrt(pb * (1 - pb) / (bn + 2.0) + pa * (1 - pa) / (an + 2.0))
    return d, d - z * se, d + z * se


@dataclass(frozen=True)
class StatisticalCanaryDecision:
    status: str
    ratio: float
    stage_index: int
    baseline_n: int
    active_n: int
    success_drop: float
    success_drop_lower: float
    success_drop_upper: float
    quality_drop: float
    quality_drop_lower: float
    quality_drop_upper: float
    log_latency_increase: float
    log_latency_lower: float
    log_latency_upper: float
    p95_latency_ratio: float
    next_ratio: float | None
    confidence: float

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


class StatisticalStagedCanaryController(StagedCanaryController):
    """Stage-isolated non-inferiority gate using one-sided confidence bounds."""

    def __init__(self, path: str, *, confidence: float = 0.95, **kwargs):
        super().__init__(path, **kwargs)
        if not 0.5 < confidence < 1.0:
            raise ValueError("confidence must be in (0.5,1)")
        self.confidence = float(confidence)
        # Conservative family-wise allocation across success/quality/latency and 3 A/B stages.
        alpha = 1.0 - self.confidence
        per_bound_alpha = alpha / 9.0
        self.bound_confidence = 1.0 - per_bound_alpha
        self.z = NormalDist().inv_cdf(self.bound_confidence)

    def _is_decision_checkpoint(self, bn: int, an: int) -> bool:
        look = min(int(bn), int(an))
        if look < self.min_per_arm:
            return False
        q, r = divmod(look, self.min_per_arm)
        return r == 0 and q > 0 and (q & (q - 1)) == 0

    def ingest(self, telemetry) -> bool:
        st = self.state(telemetry.capability_id, telemetry.candidate_digest)
        if not st["exists"] or st["status"] != "running":
            return False
        if hasattr(telemetry, "stage_ratio") and abs(float(telemetry.stage_ratio) - float(st["ratio"])) > 1e-12:
            return False
        return super().ingest(telemetry)

    def reset_after_release(self, capability_id: str, candidate_digest: str) -> Dict[str, object]:
        with closing(sqlite3.connect(self.path)) as con:
            con.execute("DELETE FROM canary_obs WHERE capability_id=? AND candidate_digest=?",
                        (capability_id, candidate_digest))
            con.execute("UPDATE canary_state SET stage_index=0,status='running',updated_at=strftime('%s','now') WHERE capability_id=? AND candidate_digest=?",
                        (capability_id, candidate_digest))
            con.commit()
        return self.state(capability_id, candidate_digest)

    def evaluate(self, capability_id: str, candidate_digest: str) -> StatisticalCanaryDecision:
        st = self.state(capability_id, candidate_digest)
        if not st["exists"]:
            raise ValueError("canary not started")
        idx = int(st["stage_index"]); ratio = float(st["ratio"])
        if st["status"] in {"rolled_back", "quarantined", "complete"}:
            status = str(st["status"])
            if status == "complete": ratio = 1.0
            return StatisticalCanaryDecision(status, ratio, idx, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0, 1.0 if status == 'complete' else None, self.bound_confidence)
        with closing(sqlite3.connect(self.path)) as con:
            rows = con.execute(
                "SELECT arm,success,quality,latency FROM canary_obs WHERE capability_id=? AND candidate_digest=? AND stage_index=?",
                (capability_id, candidate_digest, idx),
            ).fetchall()
        b = [r for r in rows if r[0] == "baseline"]; a = [r for r in rows if r[0] == "active"]
        bn, an = len(b), len(a)
        if bn < self.min_per_arm or an < self.min_per_arm or not self._is_decision_checkpoint(bn, an):
            return StatisticalCanaryDecision("monitoring", ratio, idx, bn, an, 0, -1, 1, 0, -1, 1, 0, -1, 1, 1.0, ratio, self.bound_confidence)

        bs = sum(int(r[1]) for r in b); ass = sum(int(r[1]) for r in a)
        sd, s_lo, s_hi = _success_drop_bounds(bs, bn, ass, an, self.z)
        bq = [float(r[2]) for r in b]; aq = [float(r[2]) for r in a]
        qd, q_lo, q_hi = _mean_diff_bounds(bq, aq, self.z)
        bl = [math.log1p(float(r[3])) for r in b]; al = [math.log1p(float(r[3])) for r in a]
        # latency regression is active-baseline, so reverse the sign from helper output
        neg_d, neg_lo, neg_hi = _mean_diff_bounds(bl, al, self.z)
        ld, l_lo, l_hi = -neg_d, -neg_hi, -neg_lo
        bp95 = _p95(float(r[3]) for r in b); ap95 = _p95(float(r[3]) for r in a)
        p95_ratio = ap95 / bp95 if bp95 > 0 else (1.0 if ap95 == 0 else 1_000_000_000.0)
        latency_margin = math.log(self.max_latency_ratio)

        regression = (
            s_lo > self.max_success_drop or
            q_lo > self.max_quality_drop or
            l_lo > latency_margin or
            p95_ratio > self.max_latency_ratio * 1.25
        )
        safe = (
            s_hi <= self.max_success_drop and
            q_hi <= self.max_quality_drop and
            l_hi <= latency_margin and
            p95_ratio <= self.max_latency_ratio
        )
        if regression:
            status = "rollback_required"; next_ratio = None
        elif not safe:
            status = "monitoring"; next_ratio = ratio
        elif idx >= len(self.stages) - 2:
            # A healthy 50% stage is the last A/B gate; 100% has no baseline arm.
            self._set_state(capability_id, candidate_digest, len(self.stages) - 1, "complete")
            status = "complete"; next_ratio = 1.0
        else:
            next_idx = idx + 1; next_ratio = self.stages[next_idx]
            self._set_state(capability_id, candidate_digest, next_idx, "running")
            status = "advance"
        return StatisticalCanaryDecision(status, ratio, idx, bn, an, sd, s_lo, s_hi,
                                          qd, q_lo, q_hi, ld, l_lo, l_hi, p95_ratio,
                                          next_ratio, self.bound_confidence)
