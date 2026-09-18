from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .models import FailureCluster, PriorityDecision


@dataclass(frozen=True)
class EvidencePolicy:
    """Minimum evidence required before requesting a new/modified Skill.

    This gate is deliberately stricter than the ranking engine. Ranking answers
    'what looks most valuable?'; this gate answers 'is there enough verified
    evidence to act on it without overfitting?'.
    """

    min_verified_cases: int = 20
    min_cluster_failures: int = 3
    min_family_cases: int = 5
    min_failure_rate: float = 0.20
    min_priority_score: float = 0.15


@dataclass(frozen=True)
class EvidenceDecision:
    ready: bool
    reason: str
    verified_cases: int
    cluster_failures: int
    family_cases: int
    failure_rate: float
    priority_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceGate:
    def __init__(self, policy: Optional[EvidencePolicy] = None):
        self.policy = policy or EvidencePolicy()

    def evaluate(self, *, verified_cases: int, cluster: FailureCluster,
                 priority: PriorityDecision) -> EvidenceDecision:
        p = self.policy
        failure_rate = 1.0 - cluster.success_rate
        checks = [
            (verified_cases >= p.min_verified_cases,
             f"verified_cases<{p.min_verified_cases}"),
            (cluster.count >= p.min_cluster_failures,
             f"cluster_failures<{p.min_cluster_failures}"),
            (cluster.total_in_family >= p.min_family_cases,
             f"family_cases<{p.min_family_cases}"),
            (failure_rate >= p.min_failure_rate,
             f"failure_rate<{p.min_failure_rate:.2f}"),
            (priority.score >= p.min_priority_score,
             f"priority_score<{p.min_priority_score:.2f}"),
        ]
        failed = [reason for ok, reason in checks if not ok]
        return EvidenceDecision(
            ready=not failed,
            reason="ready" if not failed else ";".join(failed),
            verified_cases=verified_cases,
            cluster_failures=cluster.count,
            family_cases=cluster.total_in_family,
            failure_rate=failure_rate,
            priority_score=priority.score,
        )
