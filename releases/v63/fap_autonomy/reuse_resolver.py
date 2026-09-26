from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional

from .failure_analyzer import FailureClusterAnalyzer
from .models import BenchmarkResult, GapType, PriorityDecision


GAP_SKILL_HINTS = {
    GapType.MATH_GAP: ("math", "reason"),
    GapType.CODE_GAP: ("coding", "reason"),
    GapType.KNOWLEDGE_GAP: ("knowledge", "research"),
    GapType.REASONING_GAP: ("reason",),
    GapType.PLANNING_GAP: ("planning", "reason"),
    GapType.MEMORY_GAP: ("memory",),
    GapType.LANGUAGE_GENERATION_GAP: ("verbalize", "local_llm"),
    GapType.VERIFICATION_GAP: ("critic",),
    GapType.SEMANTIC_GAP: ("knowledge", "reason"),
    GapType.TOOL_USE_GAP: ("research", "reason"),
    GapType.VISION_GAP: ("vision", "image"),
    GapType.IMAGE_GENERATION_GAP: ("visual_forge", "image_generation"),
    GapType.WEB_DESIGN_GAP: ("web", "coding"),
    GapType.LONG_HORIZON_GAP: ("planning", "reason", "memory"),
}


@dataclass(frozen=True)
class ReuseAssessment:
    mode: str
    target_skill: Optional[str]
    failure_rows: int
    skill_presence_rate: float
    observed_skill_counts: Dict[str, int]

    def to_dict(self):
        return asdict(self)


class CapabilityReuseResolver:
    """Infers whether a measured gap should extend an existing V59 skill.

    This is advisory only; the concrete Skill Factory/Registry remains authoritative.
    """

    def __init__(self, analyzer: Optional[FailureClusterAnalyzer] = None, threshold: float = 0.50):
        self.analyzer = analyzer or FailureClusterAnalyzer()
        self.threshold = threshold

    def assess(self, decision: PriorityDecision, results: Iterable[BenchmarkResult]) -> ReuseAssessment:
        target_key = decision.candidate.metadata.get("cluster_key")
        rows: List[BenchmarkResult] = []
        for r in results:
            if r.success:
                continue
            e = self.analyzer.classify(r)
            key = "/".join((e.gap.value, *e.hierarchy))
            if key == target_key:
                rows.append(r)

        counts: Dict[str, int] = {}
        for r in rows:
            for s in r.metadata.get("selected_skills", []) or []:
                s = str(s)
                counts[s] = counts.get(s, 0) + 1

        hints = GAP_SKILL_HINTS.get(decision.candidate.gap, ())
        target = None
        best = 0
        for s in hints:
            n = counts.get(s, 0)
            if n > best:
                best = n
                target = s
        rate = best / len(rows) if rows else 0.0
        mode = "extend_existing_skill" if target and rate >= self.threshold else "new_skill_candidate"
        return ReuseAssessment(mode, target if mode == "extend_existing_skill" else None,
                               len(rows), rate, counts)
