from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class GapType(str, Enum):
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"
    SEMANTIC_GAP = "SEMANTIC_GAP"
    REASONING_GAP = "REASONING_GAP"
    LONG_HORIZON_GAP = "LONG_HORIZON_GAP"
    MATH_GAP = "MATH_GAP"
    CODE_GAP = "CODE_GAP"
    VISION_GAP = "VISION_GAP"
    IMAGE_GENERATION_GAP = "IMAGE_GENERATION_GAP"
    WEB_DESIGN_GAP = "WEB_DESIGN_GAP"
    TOOL_USE_GAP = "TOOL_USE_GAP"
    MEMORY_GAP = "MEMORY_GAP"
    VERIFICATION_GAP = "VERIFICATION_GAP"
    LANGUAGE_GENERATION_GAP = "LANGUAGE_GENERATION_GAP"
    PLANNING_GAP = "PLANNING_GAP"
    UNKNOWN_GAP = "UNKNOWN_GAP"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    domain: str
    task: str
    expected: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkResult:
    case: BenchmarkCase
    success: bool
    actual: Any = None
    error: str = ""
    latency_ms: float = 0.0
    teacher_used: bool = False
    verified: bool = False
    verifier_confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FailureEvent:
    case_id: str
    gap: GapType
    hierarchy: Tuple[str, ...]
    domain: str
    task: str
    error: str
    teacher_used: bool
    latency_ms: float
    repairability: float
    generality: float
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureCluster:
    key: str
    gap: GapType
    hierarchy: Tuple[str, ...]
    count: int = 0
    successes_in_family: int = 0
    total_in_family: int = 0
    teacher_uses: int = 0
    latency_ms_sum: float = 0.0
    repairability_sum: float = 0.0
    generality_sum: float = 0.0
    samples: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successes_in_family / self.total_in_family if self.total_in_family else 0.0

    @property
    def teacher_dependency(self) -> float:
        return self.teacher_uses / self.total_in_family if self.total_in_family else 0.0

    @property
    def mean_latency_ms(self) -> float:
        return self.latency_ms_sum / self.count if self.count else 0.0

    @property
    def repairability(self) -> float:
        return self.repairability_sum / self.count if self.count else 0.0

    @property
    def generality(self) -> float:
        return self.generality_sum / self.count if self.count else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.update({
            "gap": self.gap.value,
            "success_rate": self.success_rate,
            "teacher_dependency": self.teacher_dependency,
            "mean_latency_ms": self.mean_latency_ms,
            "repairability": self.repairability,
            "generality": self.generality,
        })
        return d


@dataclass(frozen=True)
class CapabilityCandidate:
    capability_id: str
    gap: GapType
    hierarchy: Tuple[str, ...]
    frequency: float
    failure_severity: float
    teacher_dependency: float
    repairability: float
    generality: float
    estimated_code_kb: float
    estimated_ram_mb: float
    estimated_latency_ms: float
    regression_risk: float
    existing_skill_match: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PriorityDecision:
    candidate: CapabilityCandidate
    expected_gain: float
    cost: float
    score: float
    reasons: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.candidate.capability_id,
            "gap": self.candidate.gap.value,
            "hierarchy": list(self.candidate.hierarchy),
            "expected_gain": self.expected_gain,
            "cost": self.cost,
            "score": self.score,
            "reasons": list(self.reasons),
            "existing_skill_match": self.candidate.existing_skill_match,
        }


@dataclass(frozen=True)
class ImprovementBudget:
    max_generated_code_kb: float = 256.0
    max_test_seconds: float = 60.0
    max_ram_mb: float = 256.0
    max_disk_mb: float = 32.0
    retry_count: int = 2
    max_regression: float = 0.02


@dataclass
class LifecycleRecord:
    capability_id: str
    state: str = "ephemeral"
    verified_trials: int = 0
    verified_successes: int = 0
    verified_failures: int = 0
    confidence_sum: float = 0.0
    dev_score: float = 0.0
    holdout_score: float = 0.0
    regression_delta: float = 0.0
    resource_ok: bool = False

    @property
    def success_rate(self) -> float:
        return self.verified_successes / self.verified_trials if self.verified_trials else 0.0

    @property
    def mean_confidence(self) -> float:
        return self.confidence_sum / self.verified_trials if self.verified_trials else 0.0
