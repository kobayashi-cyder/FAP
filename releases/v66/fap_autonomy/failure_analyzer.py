from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from .models import BenchmarkResult, FailureCluster, FailureEvent, GapType


class FailureClusterAnalyzer:
    """Converts failed tasks into hierarchical capability-gap clusters.

    Classification uses task/domain/error/metadata signals, never benchmark answers.
    The hierarchy remains structural (e.g. MATH_GAP/word_problem/quantity_relation/multi_step).
    """

    DOMAIN_TO_GAP = {
        "math": GapType.MATH_GAP,
        "code": GapType.CODE_GAP,
        "coding": GapType.CODE_GAP,
        "vision": GapType.VISION_GAP,
        "image": GapType.IMAGE_GENERATION_GAP,
        "image_generation": GapType.IMAGE_GENERATION_GAP,
        "web": GapType.WEB_DESIGN_GAP,
        "web_design": GapType.WEB_DESIGN_GAP,
        "tool": GapType.TOOL_USE_GAP,
        "memory": GapType.MEMORY_GAP,
        "knowledge": GapType.KNOWLEDGE_GAP,
        "semantic": GapType.SEMANTIC_GAP,
        "reasoning": GapType.REASONING_GAP,
        "planning": GapType.PLANNING_GAP,
        "language": GapType.LANGUAGE_GENERATION_GAP,
        "verification": GapType.VERIFICATION_GAP,
        "long_reasoning": GapType.LONG_HORIZON_GAP,
    }

    def classify(self, result: BenchmarkResult) -> FailureEvent:
        text = " ".join([
            result.case.domain,
            result.case.task,
            result.error,
            str(result.case.metadata),
            str(result.metadata),
        ]).lower()
        gap = self._gap_from_signals(result.case.domain.lower(), text)
        hierarchy = self._hierarchy(gap, text, result.case.metadata, result.metadata)
        repairability = self._repairability(gap, result)
        generality = self._generality(gap, hierarchy, result)
        return FailureEvent(
            case_id=result.case.case_id,
            gap=gap,
            hierarchy=hierarchy,
            domain=result.case.domain,
            task=result.case.task,
            error=result.error,
            teacher_used=result.teacher_used,
            latency_ms=result.latency_ms,
            repairability=repairability,
            generality=generality,
            evidence={"metadata": result.metadata, "case_metadata": result.case.metadata},
        )

    def cluster(self, results: Iterable[BenchmarkResult]) -> List[FailureCluster]:
        all_results = list(results)
        failures = [r for r in all_results if not r.success]
        clusters: Dict[str, FailureCluster] = {}
        family_stats: Dict[Tuple[GapType, Tuple[str, ...]], List[int]] = defaultdict(lambda: [0, 0, 0])

        classified_failures = [self.classify(r) for r in failures]
        for r in all_results:
            pseudo = self.classify(r) if not r.success else self._classify_success_family(r)
            fam = (pseudo.gap, pseudo.hierarchy)
            family_stats[fam][1] += 1
            family_stats[fam][0] += int(r.success)
            family_stats[fam][2] += int(r.teacher_used)

        for e in classified_failures:
            key = "/".join((e.gap.value, *e.hierarchy))
            c = clusters.get(key)
            if c is None:
                c = clusters[key] = FailureCluster(key=key, gap=e.gap, hierarchy=e.hierarchy)
            c.count += 1
            fam = family_stats[(e.gap, e.hierarchy)]
            c.successes_in_family, c.total_in_family, c.teacher_uses = fam
            c.latency_ms_sum += e.latency_ms
            c.repairability_sum += e.repairability
            c.generality_sum += e.generality
            if len(c.samples) < 5:
                c.samples.append(e.case_id)
        return sorted(clusters.values(), key=lambda c: (-c.count, c.key))

    def _classify_success_family(self, r: BenchmarkResult) -> FailureEvent:
        text = " ".join([r.case.domain, r.case.task, str(r.case.metadata), str(r.metadata)]).lower()
        gap = self._gap_from_signals(r.case.domain.lower(), text)
        hierarchy = self._hierarchy(gap, text, r.case.metadata, r.metadata)
        return FailureEvent(r.case.case_id, gap, hierarchy, r.case.domain, r.case.task, "", r.teacher_used,
                            r.latency_ms, 0.5, 0.5, {})

    def _gap_from_signals(self, domain: str, text: str) -> GapType:
        explicit = self.DOMAIN_TO_GAP.get(domain)
        if explicit:
            return explicit
        rules = [
            (GapType.IMAGE_GENERATION_GAP, r"image.?gen|inpaint|diffusion|rendered image"),
            (GapType.WEB_DESIGN_GAP, r"html|css|responsive|browser render|layout|accessibility"),
            (GapType.VISION_GAP, r"ocr|screenshot|object count|visual|image input"),
            (GapType.CODE_GAP, r"compile|syntaxerror|traceback|repository|unit test|build fail"),
            (GapType.MATH_GAP, r"equation|percentage|ratio|arithmetic|geometry|probability|unit conversion|gsm"),
            (GapType.TOOL_USE_GAP, r"tool|schema|argument|side effect|api"),
            (GapType.MEMORY_GAP, r"memory|recall|context lost|forgot"),
            (GapType.VERIFICATION_GAP, r"verify|critic|false positive|unsupported|hallucin"),
            (GapType.LONG_HORIZON_GAP, r"long.?horizon|many steps|dependency chain|subgoal"),
            (GapType.PLANNING_GAP, r"plan|schedule|subgoal|dependency"),
            (GapType.KNOWLEDGE_GAP, r"unknown fact|knowledge|freshness|source"),
            (GapType.SEMANTIC_GAP, r"semantic|analogy|lexical|concept relation"),
            (GapType.LANGUAGE_GENERATION_GAP, r"grammar|natural language|verbalize|fluency"),
            (GapType.REASONING_GAP, r"reason|logic|counterexample|inference"),
        ]
        for gap, pattern in rules:
            if re.search(pattern, text):
                return gap
        return GapType.UNKNOWN_GAP

    def _hierarchy(self, gap: GapType, text: str, case_meta: dict, result_meta: dict) -> Tuple[str, ...]:
        supplied = result_meta.get("gap_path") or case_meta.get("gap_path")
        if supplied:
            if isinstance(supplied, str):
                return tuple(x for x in supplied.split("/") if x)
            return tuple(str(x) for x in supplied)
        if gap is GapType.MATH_GAP:
            levels = []
            if any(k in text for k in ("word problem", "story problem", "文章題")):
                levels.append("word_problem")
            if any(k in text for k in ("quantity", "relation", "ratio", "percent")):
                levels.append("quantity_relation")
            if any(k in text for k in ("multi-step", "multi step", "several steps")):
                levels.append("multi_step")
            return tuple(levels or ["general"])
        if gap is GapType.CODE_GAP:
            if "compile" in text or "syntax" in text:
                return ("repository", "compile_repair")
            if "test" in text:
                return ("repository", "test_repair")
            return ("repository", "implementation")
        if gap is GapType.VISION_GAP:
            if "object count" in text or "count" in text:
                return ("perception", "object_counting")
            if "ocr" in text or "text" in text:
                return ("perception", "text_layout")
            return ("perception", "general")
        if gap is GapType.WEB_DESIGN_GAP:
            if "responsive" in text:
                return ("layout", "responsive")
            if "accessibility" in text:
                return ("evaluation", "accessibility")
            return ("layout", "visual_hierarchy")
        if gap is GapType.LONG_HORIZON_GAP:
            return ("workspace", "dependency_tracking")
        return ("general",)

    def _repairability(self, gap: GapType, result: BenchmarkResult) -> float:
        base = {
            GapType.MATH_GAP: 0.85,
            GapType.CODE_GAP: 0.80,
            GapType.WEB_DESIGN_GAP: 0.75,
            GapType.TOOL_USE_GAP: 0.82,
            GapType.VERIFICATION_GAP: 0.72,
            GapType.KNOWLEDGE_GAP: 0.55,
            GapType.SEMANTIC_GAP: 0.50,
            GapType.VISION_GAP: 0.55,
            GapType.IMAGE_GENERATION_GAP: 0.35,
            GapType.LONG_HORIZON_GAP: 0.50,
        }.get(gap, 0.60)
        if result.error and any(k in result.error.lower() for k in ("timeout", "oom", "out of memory")):
            base -= 0.15
        return max(0.05, min(1.0, base))

    def _generality(self, gap: GapType, hierarchy: Tuple[str, ...], result: BenchmarkResult) -> float:
        if result.case.metadata.get("one_off"):
            return 0.15
        base = 0.65
        if gap in {GapType.MATH_GAP, GapType.REASONING_GAP, GapType.CODE_GAP, GapType.TOOL_USE_GAP,
                   GapType.SEMANTIC_GAP, GapType.LONG_HORIZON_GAP}:
            base += 0.15
        if hierarchy and hierarchy[-1] == "general":
            base += 0.05
        return min(1.0, base)
