from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable

from .failure_analyzer import FailureClusterAnalyzer
from .models import BenchmarkResult, GapType


MATRIX_KEYS = {
    GapType.LANGUAGE_GENERATION_GAP: "language",
    GapType.KNOWLEDGE_GAP: "knowledge",
    GapType.MATH_GAP: "math",
    GapType.REASONING_GAP: "logic_reasoning",
    GapType.LONG_HORIZON_GAP: "long_reasoning",
    GapType.CODE_GAP: "coding",
    GapType.VISION_GAP: "vision",
    GapType.IMAGE_GENERATION_GAP: "image_generation",
    GapType.WEB_DESIGN_GAP: "web_design",
    GapType.TOOL_USE_GAP: "tool_use",
    GapType.MEMORY_GAP: "memory",
    GapType.VERIFICATION_GAP: "verification",
    GapType.PLANNING_GAP: "planning",
    GapType.SEMANTIC_GAP: "semantic",
}


class OperationalCapabilityMatrix:
    """Descriptive matrix from verified operational outcomes only.

    It is not a substitute for official benchmark scores. Missing categories remain null.
    """

    def __init__(self, analyzer=None):
        self.analyzer = analyzer or FailureClusterAnalyzer()

    def build(self, results: Iterable[BenchmarkResult]) -> Dict[str, Any]:
        stats = defaultdict(lambda: {"cases": 0, "passed": 0, "teacher": 0, "latency": 0.0})
        for r in results:
            e = self.analyzer._classify_success_family(r) if r.success else self.analyzer.classify(r)
            key = MATRIX_KEYS.get(e.gap, "unknown")
            s = stats[key]
            s["cases"] += 1
            s["passed"] += int(r.success)
            s["teacher"] += int(r.teacher_used)
            s["latency"] += r.latency_ms

        names = list(MATRIX_KEYS.values()) + ["self_learning"]
        out = {}
        for name in names:
            s = stats.get(name)
            if not s or not s["cases"]:
                out[name] = None
                continue
            n = s["cases"]
            out[name] = {
                "source": "verified_operational_outcomes",
                "cases": n,
                "score": s["passed"] / n,
                "teacher_dependency": s["teacher"] / n,
                "mean_latency_ms": s["latency"] / n,
            }
        out["self_learning"] = {
            "source": "mechanism_validation",
            "cases": None,
            "score": None,
            "note": "Report release tests separately; operational outcomes do not directly score the self-learning mechanism.",
        }
        return out
