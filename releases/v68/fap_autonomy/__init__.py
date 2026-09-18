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

# V63 activation / rollback layer
from .provenance import ProvenanceLedger
from .activation_manager import ActivationManager
from .skill_factory_adapter import SkillFactoryOutputAdapter
from .post_activation_monitor import PostActivationMonitor
from .v63_closed_loop import V63ClosedLoopCoordinator

# V64 runtime dispatch / canary layer
from .runtime_dispatcher import ActiveRuntimeDispatcher, SandboxedRuntimeBridge, RuntimeDispatchError
from .ab_observer import ABObserver, ABDecision
from .demotion_feedback import DemotionFeedback
from .android_state_sync import AndroidStateSync
from .v64_coordinator import V64Coordinator

# V65 staged operational rollout layer
from .telemetry import RuntimeTelemetry, normalize_runtime_telemetry, parse_runtime_telemetry_json
from .canary_controller import CanaryDecision, StagedCanaryController
from .quarantine import QuarantineLedger
from .trusted_runner import TrustedSandboxRunner
from .skill_factory_worker import SkillFactoryHandoff
from .android_v65_sync import AndroidV65StateSync
from .v65_coordinator import V65Coordinator

__all__ += [
    "RuntimeTelemetry", "normalize_runtime_telemetry", "parse_runtime_telemetry_json",
    "CanaryDecision", "StagedCanaryController", "QuarantineLedger", "TrustedSandboxRunner",
    "SkillFactoryHandoff", "AndroidV65StateSync", "V65Coordinator",
]

# V66 attested production evidence / statistical canary / repair loop
from .attestation import AttestationError, AttestationVerifier, AttestedSandboxRunner, VerifiedAttestation
from .telemetry_v66 import AttestedRuntimeTelemetry, FAPTelemetryEmitter, TelemetryVerifier, normalize_attested_telemetry
from .statistical_canary import StatisticalCanaryDecision, StatisticalStagedCanaryController
from .quarantine_release import EvidenceQuarantineLedger
from .repair_bridge import QuarantineRepairEmitter
from .production_matrix import ProductionCapabilityMatrix
from .v66_coordinator import V66Coordinator

__all__ += [
    "AttestationError", "AttestationVerifier", "AttestedSandboxRunner", "VerifiedAttestation",
    "AttestedRuntimeTelemetry", "FAPTelemetryEmitter", "TelemetryVerifier", "normalize_attested_telemetry",
    "StatisticalCanaryDecision", "StatisticalStagedCanaryController", "EvidenceQuarantineLedger",
    "QuarantineRepairEmitter", "ProductionCapabilityMatrix", "V66Coordinator",
]

# V67 native repository code factory
from .repo_context import RepositoryContextBuilder, RepositoryContext, RepoFile, RepositoryContextError
from .code_ir import FunctionIR, CodeIRError
from .patch_engine import FilePatch, PatchSet, RepositoryPatchApplier, PatchError
from .code_lineage import CodeLineageLedger
from .native_patch_generator import NativePatchGenerator, GenerationError
from .repository_code_factory import NativeRepositoryCodeFactory, LocalValidationRunner, CodeFactoryError
from .v67_coordinator import V67CodeFactoryCoordinator

__all__ += [
    "RepositoryContextBuilder", "RepositoryContext", "RepoFile", "RepositoryContextError",
    "FunctionIR", "CodeIRError", "FilePatch", "PatchSet", "RepositoryPatchApplier", "PatchError",
    "CodeLineageLedger", "NativePatchGenerator", "GenerationError", "NativeRepositoryCodeFactory",
    "LocalValidationRunner", "CodeFactoryError", "V67CodeFactoryCoordinator",
]


# V68 task-plan / AST patch / candidate-race code generation
from .task_planner import TaskPlan, TaskPlanError, NaturalLanguageTaskPlanner, expression_text_to_ir
from .ast_patch_planner import (
    ASTPatchError, append_function_patch, qualified_name_patch, reexport_symbol_patch,
    keyword_compatibility_patches, syntax_expected_colon_patch,
)
from .diagnostic_repair import DiagnosticRepairPlanner, DiagnosticRepairError
from .candidate_race import CandidateRace
from .v68_code_factory import V68CodeFactory
from .v68_coordinator import V68CodeFactoryCoordinator

__all__ += [
    "TaskPlan", "TaskPlanError", "NaturalLanguageTaskPlanner", "expression_text_to_ir",
    "ASTPatchError", "append_function_patch", "qualified_name_patch", "reexport_symbol_patch",
    "keyword_compatibility_patches", "syntax_expected_colon_patch",
    "DiagnosticRepairPlanner", "DiagnosticRepairError", "CandidateRace",
    "V68CodeFactory", "V68CodeFactoryCoordinator",
]
