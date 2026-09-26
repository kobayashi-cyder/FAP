from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Optional

from .models import CapabilityCandidate, FailureCluster, PriorityDecision


class CapabilityPriorityEngine:
    """Ranks missing capabilities by expected generalizable gain per bounded cost.

    The score intentionally avoids raw failure-count ranking. All resource terms are normalized
    so code bytes do not numerically swamp RAM/latency. Existing matching skills receive a penalty
    because extending/reusing a skill is preferred to duplicate implementation.
    """

    def __init__(self, cost_weights: Optional[Mapping[str, float]] = None):
        self.cost_weights = dict(cost_weights or {
            "code": 0.28,
            "ram": 0.28,
            "latency": 0.20,
            "regression": 0.24,
        })

    def from_clusters(self, clusters: Iterable[FailureCluster], total_cases: int,
                      cost_hints: Optional[Mapping[str, Dict[str, float]]] = None,
                      existing_skill_matches: Optional[Mapping[str, str]] = None) -> List[CapabilityCandidate]:
        total_cases = max(total_cases, 1)
        hints = cost_hints or {}
        existing = existing_skill_matches or {}
        candidates = []
        for c in clusters:
            h = hints.get(c.key, {})
            failure_severity = 1.0 - c.success_rate
            candidates.append(CapabilityCandidate(
                capability_id=self._capability_id(c),
                gap=c.gap,
                hierarchy=c.hierarchy,
                frequency=c.count / total_cases,
                failure_severity=failure_severity,
                teacher_dependency=c.teacher_dependency,
                repairability=c.repairability,
                generality=c.generality,
                estimated_code_kb=float(h.get("code_kb", 32.0)),
                estimated_ram_mb=float(h.get("ram_mb", 8.0)),
                estimated_latency_ms=float(h.get("latency_ms", max(1.0, c.mean_latency_ms * 0.05))),
                regression_risk=float(h.get("regression_risk", 0.08)),
                existing_skill_match=existing.get(c.key),
                metadata={"cluster_key": c.key, "count": c.count},
            ))
        return candidates

    def rank(self, candidates: Iterable[CapabilityCandidate]) -> List[PriorityDecision]:
        decisions = [self.score(c) for c in candidates]
        return sorted(decisions, key=lambda d: (-d.score, d.candidate.capability_id))

    def score(self, c: CapabilityCandidate) -> PriorityDecision:
        # Frequency gets sqrt compression: recurrent failures matter, but high count alone cannot dominate.
        expected_gain = (
            math.sqrt(max(0.0, c.frequency))
            * (0.34 * c.failure_severity + 0.21 * c.teacher_dependency + 0.25 * c.repairability + 0.20 * c.generality)
        )
        code = min(c.estimated_code_kb / 256.0, 4.0)
        ram = min(c.estimated_ram_mb / 256.0, 4.0)
        latency = min(c.estimated_latency_ms / 250.0, 4.0)
        regression = min(max(c.regression_risk, 0.0), 1.0)
        cost = 0.04 + (
            self.cost_weights["code"] * code
            + self.cost_weights["ram"] * ram
            + self.cost_weights["latency"] * latency
            + self.cost_weights["regression"] * regression
        )
        duplicate_penalty = 0.45 if c.existing_skill_match else 1.0
        score = (expected_gain / cost) * duplicate_penalty
        reasons = [
            f"frequency={c.frequency:.3f}",
            f"failure_severity={c.failure_severity:.3f}",
            f"teacher_dependency={c.teacher_dependency:.3f}",
            f"repairability={c.repairability:.3f}",
            f"generality={c.generality:.3f}",
        ]
        if c.existing_skill_match:
            reasons.append(f"reuse_preferred={c.existing_skill_match}")
        return PriorityDecision(c, expected_gain, cost, score, tuple(reasons))

    @staticmethod
    def _capability_id(c: FailureCluster) -> str:
        suffix = "_".join(c.hierarchy)
        return (c.gap.value.lower() + ("__" + suffix if suffix else "")).replace("-", "_")
