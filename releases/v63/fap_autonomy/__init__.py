"""FAP autonomous capability development patch.

Designed as an additive layer: it does not merge FAP Local/FAP-/Student/Knowledge/Teacher,
and it does not auto-import unverified generated code.
"""
from .models import (
    GapType, BenchmarkCase, BenchmarkResult, FailureEvent, FailureCluster,
    CapabilityCandidate, PriorityDecision, ImprovementBudget, LifecycleRecord,
)
from .failure_analyzer import FailureClusterAnalyzer
from .priority_engine import CapabilityPriorityEngine
from .lifecycle import VerificationLifecycle
from .loop import AutonomousCapabilityLoop

__all__ = [
    "GapType", "BenchmarkCase", "BenchmarkResult", "FailureEvent", "FailureCluster",
    "CapabilityCandidate", "PriorityDecision", "ImprovementBudget", "LifecycleRecord",
    "FailureClusterAnalyzer", "CapabilityPriorityEngine", "VerificationLifecycle",
    "AutonomousCapabilityLoop",
]

# V61 operational capability planning
from .evidence_gate import EvidenceGate, EvidencePolicy, EvidenceDecision
from .capability_spec import CapabilitySpec, CapabilitySpecBuilder
from .operational_ledger import OperationalLedger
from .v59_operational import V59OperationalPlanner
from .reuse_resolver import CapabilityReuseResolver, ReuseAssessment
from .operational_matrix import OperationalCapabilityMatrix
from .request_queue import SkillFactoryRequestQueue

# V62 closed-loop candidate promotion
from .promotion_ledger import PromotionLedger, PromotionState, digest_tree
from .holdout_seal import HoldoutSeal
from .verified_registry import VerifiedSkillRegistry
from .candidate_pipeline import CandidatePromotionPipeline

# V63 activation, runtime monitoring and rollback
from .activation import AtomicActivationManager, ActivationError
from .post_activation_monitor import PostActivationMonitor, MonitorDecision
from .provenance import PatchHistory
from .skill_factory_bridge import SkillFactoryOutputAdapter, SkillFactoryCommandBridge, SkillFactoryOutputError
from .v63_orchestrator import V63Orchestrator
