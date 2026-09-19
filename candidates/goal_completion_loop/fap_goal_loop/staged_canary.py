from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CanaryObservation:
    """Independent evidence for one bounded rollout stage."""

    key: str
    candidate_digest: str
    success: bool
    quality_delta: float
    latency_ratio: float


class BoundedStagedCanary:
    """Conservative advisory rollout gate adapted from FCA.

    The gate can recommend advance/rollback for a candidate, but it cannot
    execute actions, promote code, or mark a FAP goal verified/completed.
    Evidence is isolated per stage so earlier successes cannot authorize a
    later stage.
    """

    stages = (0.05, 0.20, 0.50, 1.00)

    def __init__(
        self,
        candidate_digest: str,
        *,
        min_evidence: int = 4,
        min_success_rate: float = 0.95,
        min_quality_delta: float = 0.0,
        max_latency_ratio: float = 1.25,
    ) -> None:
        if not candidate_digest.strip() or min_evidence < 1:
            raise ValueError("invalid canary configuration")
        if not 0.0 <= min_success_rate <= 1.0 or max_latency_ratio <= 0.0:
            raise ValueError("invalid canary thresholds")
        self.candidate_digest = candidate_digest
        self.min_evidence = min_evidence
        self.min_success_rate = min_success_rate
        self.min_quality_delta = min_quality_delta
        self.max_latency_ratio = max_latency_ratio
        self.stage_index = 0
        self.status = "monitoring"
        self._evidence: dict[int, dict[str, CanaryObservation]] = {
            i: {} for i in range(len(self.stages))
        }

    @property
    def stage(self) -> float:
        return self.stages[self.stage_index]

    def add(self, observation: CanaryObservation) -> str:
        if self.status in {"rollback", "complete"}:
            return self.status
        if observation.candidate_digest != self.candidate_digest:
            raise ValueError("candidate digest mismatch")
        if not observation.key.strip() or observation.latency_ratio <= 0.0:
            raise ValueError("invalid canary observation")
        bucket = self._evidence[self.stage_index]
        if observation.key in bucket:
            return self.status
        bucket[observation.key] = observation
        return self.evaluate()

    def evaluate(self) -> str:
        bucket = list(self._evidence[self.stage_index].values())
        if len(bucket) < self.min_evidence:
            self.status = "monitoring"
            return self.status

        success_rate = sum(1 for item in bucket if item.success) / len(bucket)
        quality = sum(item.quality_delta for item in bucket) / len(bucket)
        latency = sorted(item.latency_ratio for item in bucket)
        p95_index = min(len(latency) - 1, max(0, ceil(0.95 * len(latency)) - 1))
        p95_latency = latency[p95_index]

        if (
            success_rate < self.min_success_rate
            or quality < self.min_quality_delta
            or p95_latency > self.max_latency_ratio
        ):
            self.status = "rollback"
            return self.status

        if self.stage_index == len(self.stages) - 1:
            self.status = "complete"
            return self.status

        self.stage_index += 1
        self.status = "monitoring"
        return "advanced"
