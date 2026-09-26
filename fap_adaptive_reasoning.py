from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
import re
from typing import Any, Mapping, Sequence


_COMPLEXITY = re.compile(
    r"(比較|理由|なぜ|設計|実装|改善|検証|証明|反例|前提|仮定|"
    r"複数|それぞれ|段階|手順|最適|トレードオフ|原因|機構|"
    r"compare|why|design|implement|verify|prove|counterexample|"
    r"assumption|multi[- ]?step|trade[- ]?off|optimi[sz]e)",
    re.I,
)
_VERIFY = re.compile(
    r"(正確|厳密|検証|確認|証明|根拠|出典|反例|安全|"
    r"diagnos|medical|薬|法律|税|投資|金融|危険|safety|"
    r"verify|evidence|source|proof|legal|finance)",
    re.I,
)
_FRESH = re.compile(
    r"(最新|今日|現在|今の|ニュース|価格|相場|天気|発売|更新|"
    r"latest|today|current|news|price|weather|release)",
    re.I,
)
_NUMERIC = re.compile(r"[-+]?d+(?:.d+)?|[=+*/×÷^]")
_SEPARATOR = re.compile(r"[
。！？!?;；]+")
_REQUIREMENT = re.compile(
    r"(必須|条件|制約|以内|以上|以下|未満|だけ|のみ|して|してください|"
    r"must|required|constraint|only|within|at least|at most)",
    re.I,
)


def _clip(value: object, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(x):
        return default
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class ReasoningAssessment:
    contract: str
    complexity: float
    epistemic_risk: float
    confidence: float
    requirement_coverage: float
    segment_coverage: float
    selected_verified: bool
    selected_grounded: bool
    needs_teacher: bool
    disagreement_count: int
    candidate_count: int
    intent_count: int
    freshness_required: bool
    verification_required: bool
    numeric_task: bool
    escalation_level: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdaptiveReasoningGovernor:
    """Fail-closed controller for adaptive compute and confidence calibration.

    The governor does not invent an answer. It inspects the already-produced
    response-series evidence, decides whether another read-only verification
    pass is warranted, and caps confidence when evidence/coverage is weak.
    """

    CONTRACT = "fap.reasoning.governor.v1"
    MAX_ESCALATION_PASSES = 2

    @staticmethod
    def _selected_row(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        execution = payload.get("response_series_execution")
        if not isinstance(execution, Mapping):
            return {}
        selected = str(execution.get("selected") or "")
        rows = execution.get("candidates")
        if not isinstance(rows, Sequence):
            return {}
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("id") or "") == selected:
                return row
        return {}

    @staticmethod
    def _intent_count(text: str) -> int:
        value = str(text or "")
        chunks = [x for x in _SEPARATOR.split(value) if x.strip()]
        separators = sum(value.count(x) for x in ("、", ",", "・", " and ", " then "))
        directives = len(re.findall(
            r"(して|してください|求め|説明|比較|列挙|実装|検証|確認|"
            r"explain|compare|list|implement|verify|calculate)",
            value,
            re.I,
        ))
        return max(1, min(16, max(len(chunks), 1 + separators // 2, directives)))

    @classmethod
    def assess(
        cls,
        text: str,
        payload: Mapping[str, Any] | None,
        *,
        dispatch_state: str = "handled",
    ) -> ReasoningAssessment:
        data = dict(payload or {})
        execution = data.get("response_series_execution")
        execution = execution if isinstance(execution, Mapping) else {}
        selected = cls._selected_row(data)

        confidence = _clip(
            data.get("confidence", selected.get("confidence", 0.5)),
            0.5,
        )
        requirement_coverage = _clip(
            selected.get("requirement_coverage", 1.0),
            1.0,
        )
        segment_coverage = _clip(
            selected.get("segment_coverage", 1.0),
            1.0,
        )
        selected_verified = bool(
            selected.get("verified")
            or data.get("verified")
            or data.get("factual_qa")
            or data.get("rule_verified")
            or data.get("derivation_verified")
            or data.get("decision_source") == "verified_arithmetic"
        )
        selected_grounded = bool(
            selected.get("grounded")
            or data.get("grounded")
            or data.get("local")
            or selected_verified
        )
        needs_teacher = bool(data.get("needs_teacher") or selected.get("needs_teacher"))

        disagreements = execution.get("verified_disagreements")
        disagreement_count = len(disagreements) if isinstance(disagreements, Sequence) else 0
        try:
            candidate_count = max(0, int(execution.get("candidate_count", 0)))
        except (TypeError, ValueError):
            candidate_count = 0

        value = str(text or "")
        intent_count = cls._intent_count(value)
        chunks = [x for x in _SEPARATOR.split(value) if x.strip()]
        chars = min(1.0, len(value) / 1800.0)
        structural = min(1.0, max(0.0, (len(chunks) - 1) / 10.0))
        semantic = 1.0 if _COMPLEXITY.search(value) else 0.0
        requirements = min(1.0, len(_REQUIREMENT.findall(value)) / 5.0)
        complexity = _clip(
            0.28 * chars
            + 0.26 * structural
            + 0.24 * semantic
            + 0.14 * requirements
            + 0.08 * min(1.0, (intent_count - 1) / 5.0)
        )

        freshness = bool(_FRESH.search(value))
        verification = bool(_VERIFY.search(value))
        numeric = bool(_NUMERIC.search(value))

        risk = 0.0
        risk += 0.28 * (1.0 - confidence)
        risk += 0.18 * complexity
        risk += 0.13 * (1.0 - requirement_coverage)
        risk += 0.10 * (1.0 - segment_coverage)
        risk += 0.10 * min(1.0, disagreement_count / 2.0)
        risk += 0.08 * float(needs_teacher)
        risk += 0.06 * float(verification and not selected_verified)
        risk += 0.04 * float(numeric and not selected_verified)
        risk += 0.03 * float(freshness and not selected_grounded)
        if dispatch_state != "handled":
            risk += 0.18
        risk = _clip(risk)

        reasons: list[str] = []
        if confidence < 0.62:
            reasons.append("low_confidence")
        if complexity >= 0.45:
            reasons.append("complex_request")
        if requirement_coverage < 0.80:
            reasons.append("requirement_gap")
        if segment_coverage < 0.80:
            reasons.append("segment_gap")
        if disagreement_count:
            reasons.append("verified_disagreement")
        if needs_teacher:
            reasons.append("needs_external_knowledge")
        if verification and not selected_verified:
            reasons.append("verification_requested_but_unverified")
        if numeric and not selected_verified:
            reasons.append("numeric_unverified")
        if freshness and not selected_grounded:
            reasons.append("freshness_without_grounding")

        if (
            selected_verified
            and confidence >= 0.88
            and disagreement_count == 0
            and requirement_coverage >= 0.90
            and segment_coverage >= 0.90
        ):
            escalation = 0
        elif risk >= 0.56 or needs_teacher or disagreement_count > 0:
            escalation = 2
        elif risk >= 0.32 or complexity >= 0.48 or verification:
            escalation = 1
        else:
            escalation = 0

        return ReasoningAssessment(
            contract=cls.CONTRACT,
            complexity=round(complexity, 4),
            epistemic_risk=round(risk, 4),
            confidence=round(confidence, 4),
            requirement_coverage=round(requirement_coverage, 4),
            segment_coverage=round(segment_coverage, 4),
            selected_verified=selected_verified,
            selected_grounded=selected_grounded,
            needs_teacher=needs_teacher,
            disagreement_count=disagreement_count,
            candidate_count=candidate_count,
            intent_count=intent_count,
            freshness_required=freshness,
            verification_required=verification,
            numeric_task=numeric,
            escalation_level=escalation,
            reasons=tuple(reasons),
        )

    @staticmethod
    def escalation_plan_kwargs(
        assessment: ReasoningAssessment,
        pass_index: int,
    ) -> dict[str, Any]:
        level = max(1, min(2, int(assessment.escalation_level)))
        pass_index = max(1, min(2, int(pass_index)))
        force = level >= 2 or pass_index >= 2
        return {
            "uncertainty": max(
                0.72 if force else 0.58,
                assessment.epistemic_risk,
                1.0 - assessment.confidence,
            ),
            "confidence": assessment.confidence,
            "disagreement": bool(
                assessment.disagreement_count
                or assessment.needs_teacher
                or force
            ),
            "counterexample": bool(
                assessment.verification_required
                or assessment.numeric_task
                or assessment.disagreement_count
                or force
            ),
            "route_candidates": 8 if force else 6,
            "verification_depth": 6 if force else 5,
            "retries": 4 if force else 2,
            "intent_count": assessment.intent_count,
            "has_route": True,
        }

    @classmethod
    def quality_score(cls, payload: Mapping[str, Any] | None) -> float:
        assessment = cls.assess("", payload or {})
        score = (
            0.34 * assessment.confidence
            + 0.20 * float(assessment.selected_verified)
            + 0.12 * float(assessment.selected_grounded)
            + 0.14 * assessment.requirement_coverage
            + 0.12 * assessment.segment_coverage
            - 0.06 * min(1.0, assessment.disagreement_count / 2.0)
            - 0.10 * float(assessment.needs_teacher)
        )
        reply = str((payload or {}).get("reply") or "")
        if len(reply.strip()) < 8:
            score -= 0.18
        return round(score, 6)

    @classmethod
    def calibrate(
        cls,
        text: str,
        payload: Mapping[str, Any],
        *,
        dispatch_state: str,
        passes: int,
        assessments: Sequence[ReasoningAssessment],
    ) -> dict[str, Any]:
        out = dict(payload)
        assessment = cls.assess(text, out, dispatch_state=dispatch_state)

        confidence = assessment.confidence
        if assessment.selected_verified and assessment.disagreement_count == 0:
            confidence = min(0.985, confidence + 0.015)
        else:
            cap = 0.86
            if assessment.verification_required or assessment.numeric_task:
                cap = min(cap, 0.78)
            if assessment.needs_teacher:
                cap = min(cap, 0.62)
            if assessment.disagreement_count:
                cap = min(cap, 0.68)
            if assessment.freshness_required and not assessment.selected_grounded:
                cap = min(cap, 0.60)
            confidence = min(confidence, cap)

        unresolved = (
            assessment.needs_teacher
            or (
                assessment.epistemic_risk >= 0.60
                and not assessment.selected_verified
                and not assessment.selected_grounded
            )
        )
        if unresolved:
            out["needs_teacher"] = True

        out["confidence"] = round(_clip(confidence, 0.5), 4)
        out["reasoning_governor"] = {
            "contract": cls.CONTRACT,
            "adaptive_compute": True,
            "passes": max(1, int(passes)),
            "final": assessment.to_dict(),
            "assessments": [a.to_dict() for a in assessments],
            "confidence_calibrated": True,
            "fail_closed": True,
            "max_escalation_passes": cls.MAX_ESCALATION_PASSES,
        }

        tags = [str(x) for x in out.get("route_tags", [])]
        for tag in (
            "adaptive-reasoning-governor",
            f"reasoning-passes:{max(1, int(passes))}",
        ):
            if tag not in tags:
                tags.append(tag)
        if unresolved and "unresolved-fail-closed" not in tags:
            tags.append("unresolved-fail-closed")
        out["route_tags"] = tags
        return out
