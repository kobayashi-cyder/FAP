from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .exchange import ExchangeCapsule


class ExchangeState(str, Enum):
    RECEIVED = "received"
    SHADOW = "shadow"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ExchangeEvidence:
    key: str
    passed: bool
    quality_delta: float = 0.0
    regression: bool = False


@dataclass
class ExchangeRecord:
    capsule: ExchangeCapsule
    state: ExchangeState = ExchangeState.RECEIVED
    evidence: dict[str, ExchangeEvidence] = field(default_factory=dict)


class ExchangeRegistry:
    """Evidence-gated cross-project mechanism registry."""

    def __init__(self, *, shadow_after: int = 1, accept_after: int = 3) -> None:
        if shadow_after < 1 or accept_after < shadow_after:
            raise ValueError("invalid exchange thresholds")
        self.shadow_after = shadow_after
        self.accept_after = accept_after
        self._records: dict[str, ExchangeRecord] = {}

    def receive(self, capsule: ExchangeCapsule) -> ExchangeState:
        self._records.setdefault(capsule.digest, ExchangeRecord(capsule))
        return self._records[capsule.digest].state

    def add_evidence(self, digest: str, evidence: ExchangeEvidence) -> ExchangeState:
        if digest not in self._records:
            raise KeyError("unknown exchange capsule")
        record = self._records[digest]
        if record.state == ExchangeState.REJECTED or evidence.key in record.evidence:
            return record.state
        record.evidence[evidence.key] = evidence
        if (not evidence.passed) or evidence.regression or evidence.quality_delta < 0.0:
            record.state = ExchangeState.REJECTED
            return record.state
        good = sum(
            1 for row in record.evidence.values()
            if row.passed and not row.regression and row.quality_delta >= 0.0
        )
        if good >= self.accept_after:
            record.state = ExchangeState.ACCEPTED
        elif good >= self.shadow_after:
            record.state = ExchangeState.SHADOW
        return record.state

    def accepted_capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(
            record.capsule.capability
            for record in self._records.values()
            if record.state == ExchangeState.ACCEPTED
        ))
