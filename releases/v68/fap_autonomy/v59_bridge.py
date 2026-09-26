from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import BenchmarkCase, BenchmarkResult


@dataclass(frozen=True)
class V59TurnOutcome:
    """Branch-neutral outcome envelope for FAP V59 Adaptive Skill Graph.

    V59 already learns routing recipes from verified success/failure. This envelope does not
    replace that mechanism; it exports the same verified outcome plus resource/Teacher signals
    to the autonomous capability analyzer.
    """
    turn_id: str
    text: str
    intent: str
    selected_skills: Sequence[str] = field(default_factory=tuple)
    verified: bool = False
    verified_success: Optional[bool] = None
    critic_ok: Optional[bool] = None
    teacher_used: bool = False
    latency_ms: float = 0.0
    error: str = ""
    domain: str = "unknown"
    topic: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_benchmark_result(self) -> Optional[BenchmarkResult]:
        # Unverified turns must not become training/failure evidence.
        if not self.verified or self.verified_success is None:
            return None
        success = bool(self.verified_success)
        if self.critic_ok is False:
            success = False
        md = dict(self.metadata)
        md.update({
            "intent": self.intent,
            "topic": self.topic,
            "selected_skills": list(self.selected_skills),
            "source": "v59_turn",
        })
        case = BenchmarkCase(
            case_id=self.turn_id,
            domain=self.domain,
            task=self.text,
            metadata=md,
        )
        return BenchmarkResult(
            case=case,
            success=success,
            error=self.error or ("verified bad" if not success else ""),
            latency_ms=self.latency_ms,
            teacher_used=self.teacher_used,
            verified=True,
            verifier_confidence=float(md.get("verifier_confidence", 1.0 if success else 0.8)),
            metadata=md,
        )


class V59OutcomeAdapter:
    """Converts V59 turn/feedback records into analyzer inputs.

    It accepts flexible field aliases because the V59 ZIP cannot be materialized in this
    environment. Target integration should bind the exact concrete fields once source is present.
    """

    @staticmethod
    def from_mapping(row: Dict[str, Any]) -> V59TurnOutcome:
        selected = row.get("selected_skills", row.get("skills", row.get("skill_set", []))) or []
        verified = bool(row.get("verified", row.get("is_verified", False)))
        success = row.get("verified_success")
        if success is None:
            feedback = row.get("verify_feedback", row.get("feedback"))
            if isinstance(feedback, str) and feedback.lower() in {"good", "bad"}:
                success = feedback.lower() == "good"
                verified = True
        return V59TurnOutcome(
            turn_id=str(row.get("turn_id", row.get("id", "unknown"))),
            text=str(row.get("text", row.get("request_text", row.get("query", "")))),
            intent=str(row.get("intent", "unknown")),
            selected_skills=tuple(str(x) for x in selected),
            verified=verified,
            verified_success=success if success is None else bool(success),
            critic_ok=row.get("critic_ok"),
            teacher_used=bool(row.get("teacher_used", row.get("teacher", False))),
            latency_ms=float(row.get("latency_ms", 0.0) or 0.0),
            error=str(row.get("error", "")),
            domain=str(row.get("domain", row.get("intent", "unknown"))),
            topic=str(row.get("topic", "")),
            metadata=dict(row.get("metadata", {})),
        )

    @classmethod
    def verified_results(cls, rows: Iterable[Dict[str, Any]]) -> List[BenchmarkResult]:
        out = []
        for row in rows:
            r = cls.from_mapping(row).to_benchmark_result()
            if r is not None:
                out.append(r)
        return out
