from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Optional

from .models import ImprovementBudget, LifecycleRecord


class VerificationLifecycle:
    """Verification-gated ephemeral -> shadow -> consolidated capability lifecycle."""

    def __init__(self, budget: Optional[ImprovementBudget] = None):
        self.budget = budget or ImprovementBudget()

    def observe(self, record: LifecycleRecord, *, success: bool, confidence: float,
                dev_score: float, holdout_score: float, regression_delta: float,
                resource_ok: bool) -> LifecycleRecord:
        record.verified_trials += 1
        record.verified_successes += int(success)
        record.verified_failures += int(not success)
        record.confidence_sum += max(0.0, min(1.0, confidence))
        record.dev_score = dev_score
        record.holdout_score = holdout_score
        record.regression_delta = regression_delta
        record.resource_ok = resource_ok

        if record.verified_failures >= 3 and record.success_rate < 0.5:
            record.state = "rejected"
            return record

        eligible = (
            resource_ok
            and regression_delta >= -self.budget.max_regression
            and holdout_score > 0.0
        )
        if eligible and record.verified_trials >= 2 and record.success_rate >= 0.5:
            record.state = "shadow"
        if (
            eligible
            and record.verified_trials >= 5
            and record.success_rate >= 0.8
            and record.mean_confidence >= 0.68
            and holdout_score >= dev_score * 0.85
        ):
            record.state = "consolidated"
        return record

    @staticmethod
    def as_dict(record: LifecycleRecord):
        d = asdict(record)
        d["success_rate"] = record.success_rate
        d["mean_confidence"] = record.mean_confidence
        return d
