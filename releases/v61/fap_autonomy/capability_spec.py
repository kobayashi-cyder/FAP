from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List

from .models import FailureCluster, GapType, ImprovementBudget, PriorityDecision


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    gap: str
    objective: str
    hierarchy: List[str]
    evidence: Dict[str, Any]
    required_interfaces: List[str]
    acceptance_tests: List[str]
    prohibitions: List[str]
    budget: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


OBJECTIVES = {
    GapType.MATH_GAP: "Generalize quantitative reasoning without answer hardcoding; structure entities, quantities, units, relations and constraints before solving.",
    GapType.CODE_GAP: "Repair and implement code with repository awareness, compile/test feedback and regression protection.",
    GapType.VISION_GAP: "Extract objects, text, layout, relations and actionable state from visual inputs into the semantic workspace.",
    GapType.IMAGE_GENERATION_GAP: "Improve native image generation quality with prompt-consistency and structural verification rather than external API substitution.",
    GapType.WEB_DESIGN_GAP: "Generate and iteratively repair web layouts using render-and-evaluate feedback.",
    GapType.TOOL_USE_GAP: "Infer tool requirements, outputs, side effects and failure modes from schemas, then verify state changes.",
    GapType.MEMORY_GAP: "Improve retrieval and task-state continuity without promoting unverified content to permanent memory.",
    GapType.VERIFICATION_GAP: "Increase independent correctness checking and reduce plausible-but-wrong outputs.",
    GapType.SEMANTIC_GAP: "Improve sparse cross-domain semantic linkage with verified latent structures and weak lexical-overlap tolerance.",
    GapType.LONG_HORIZON_GAP: "Maintain structured goals, subgoals, dependencies, evidence and rejected routes over long reasoning horizons.",
    GapType.REASONING_GAP: "Improve compositional reasoning, counterexample search and explicit verification state.",
    GapType.KNOWLEDGE_GAP: "Expand verified factual coverage while preserving source, date, confidence and freshness gates.",
    GapType.PLANNING_GAP: "Improve subgoal decomposition, dependency ordering and plan verification.",
    GapType.LANGUAGE_GENERATION_GAP: "Improve faithful natural-language realization without converting stylistic fluency into factual authority.",
    GapType.UNKNOWN_GAP: "Investigate the recurring failure family, identify the missing reusable mechanism, and validate it before consolidation.",
}


class CapabilitySpecBuilder:
    """Produces a Skill-Factory request, not executable source code."""

    def build(self, decision: PriorityDecision, cluster: FailureCluster,
              budget: ImprovementBudget, reuse: Dict[str, Any] | None = None) -> CapabilitySpec:
        c = decision.candidate
        acceptance = [
            "unit tests pass without weakening existing tests",
            "development benchmark improves or remains within regression budget",
            "untouched holdout benchmark passes the configured promotion threshold",
            "resource measurements are present for code size, RAM, disk, latency/test time",
            "repeated verified success is required before consolidated state",
        ]
        if c.gap is GapType.MATH_GAP:
            acceptance += [
                "evaluate multiple unseen quantitative word problems",
                "verify numeric result through an independent calculation path where possible",
            ]
        elif c.gap is GapType.CODE_GAP:
            acceptance += [
                "compile/build the affected target",
                "run existing regression tests plus new failure-reproduction tests",
            ]
        elif c.gap is GapType.VERIFICATION_GAP:
            acceptance += [
                "measure false-accept and false-reject rates on a held-out verifier set",
            ]

        evidence = {
            "cluster_key": cluster.key,
            "failures": cluster.count,
            "family_cases": cluster.total_in_family,
            "family_success_rate": cluster.success_rate,
            "teacher_dependency": cluster.teacher_dependency,
            "mean_latency_ms": cluster.mean_latency_ms,
            "repairability": cluster.repairability,
            "generality": cluster.generality,
            "priority_score": decision.score,
            "priority_reasons": list(decision.reasons),
            "sample_case_ids": list(cluster.samples),
        }
        return CapabilitySpec(
            capability_id=c.capability_id,
            gap=c.gap.value,
            objective=OBJECTIVES.get(c.gap, OBJECTIVES[GapType.UNKNOWN_GAP]),
            hierarchy=list(c.hierarchy),
            evidence=evidence,
            required_interfaces=[
                "existing Skill API / Skill Bus",
                "existing Skill Factory candidate interface",
                "static safety gate",
                "sandbox runner",
                "development benchmark runner",
                "untouched holdout benchmark runner",
                "verified Skill Registry promotion path",
            ],
            acceptance_tests=acceptance,
            prohibitions=[
                "benchmark answer hardcoding",
                "test weakening",
                "automatic import of unverified generated code",
                "one-success permanent learning",
                "unverified Teacher output promoted to factual Knowledge",
                "external API-only capability presented as native FAP capability",
            ],
            budget={
                "max_generated_code_kb": budget.max_generated_code_kb,
                "max_test_seconds": budget.max_test_seconds,
                "max_ram_mb": budget.max_ram_mb,
                "max_disk_mb": budget.max_disk_mb,
                "retry_count": budget.retry_count,
                "max_regression": budget.max_regression,
            },
            metadata={"kind": "skill_factory_request", "executable": False,
                      "implementation_mode": (reuse or {}).get("mode", "unknown"),
                      "target_existing_skill": (reuse or {}).get("target_skill")},
        )
