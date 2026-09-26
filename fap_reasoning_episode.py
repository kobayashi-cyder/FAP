from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from fap_adaptive_reasoning import ReasoningAssessment


@dataclass(frozen=True)
class EpisodeStep:
    pass_index: int
    phase: str
    accepted: bool
    confidence: float
    epistemic_risk: float
    verified: bool
    grounded: bool
    requirement_coverage: float
    segment_coverage: float
    disagreements: int
    needs_teacher: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReasoningEpisodeController:
    """Track and enforce long-horizon reasoning progress.

    The controller does not generate answers. It turns a sequence of bounded
    reasoning attempts into an explicit plan/verify/repair/re-verify episode
    and prevents unresolved conflicts or severe coverage gaps from being
    labeled as a clean success.
    """

    CONTRACT = "fap.reasoning.episode.v1"
    MAX_REPAIR_PASSES = 3

    @staticmethod
    def escalation_budget(assessment: ReasoningAssessment) -> int:
        level = max(0, int(assessment.escalation_level))
        if level <= 0:
            return 0
        if level == 1:
            return 1

        # A third local pass is useful only for locally repairable uncertainty.
        # Missing external knowledge should fail closed instead of burning
        # repeated local compute which cannot create new evidence.
        repairable = bool(
            assessment.disagreement_count
            or "requirement_gap" in assessment.reasons
            or "segment_gap" in assessment.reasons
            or "numeric_unverified" in assessment.reasons
            or "verification_requested_but_unverified" in assessment.reasons
        )
        external_only = bool(
            assessment.needs_teacher
            and not assessment.disagreement_count
            and not repairable
        )
        if external_only:
            return 2
        return 3 if repairable else 2

    @staticmethod
    def phase_for_pass(pass_index: int, total_budget: int) -> str:
        if pass_index <= 0:
            return "execute"
        if pass_index == 1:
            return "verify"
        if pass_index < total_budget:
            return "repair"
        return "reverify"

    @staticmethod
    def _step(
        pass_index: int,
        phase: str,
        assessment: ReasoningAssessment,
        accepted: bool,
    ) -> EpisodeStep:
        return EpisodeStep(
            pass_index=pass_index,
            phase=phase,
            accepted=bool(accepted),
            confidence=float(assessment.confidence),
            epistemic_risk=float(assessment.epistemic_risk),
            verified=bool(assessment.selected_verified),
            grounded=bool(assessment.selected_grounded),
            requirement_coverage=float(assessment.requirement_coverage),
            segment_coverage=float(assessment.segment_coverage),
            disagreements=int(assessment.disagreement_count),
            needs_teacher=bool(assessment.needs_teacher),
            reasons=tuple(assessment.reasons),
        )

    @classmethod
    def finalize(
        cls,
        payload: Mapping[str, Any],
        assessments: Sequence[ReasoningAssessment],
        *,
        accepted_passes: Sequence[int] = (),
        budget: int = 0,
    ) -> dict[str, Any]:
        out = dict(payload)
        rows = list(assessments)
        if not rows:
            return out

        accepted = {int(x) for x in accepted_passes}
        steps: list[EpisodeStep] = []
        for i, assessment in enumerate(rows):
            phase = "execute" if i == 0 else cls.phase_for_pass(i, max(1, budget))
            steps.append(cls._step(i, phase, assessment, i in accepted))

        final = rows[-1]
        reply = str(out.get("reply") or "").strip()

        unresolved_reasons: list[str] = []
        if final.disagreement_count:
            unresolved_reasons.append("verified_disagreement")
        if final.needs_teacher:
            unresolved_reasons.append("needs_external_knowledge")
        if final.requirement_coverage < 0.70:
            unresolved_reasons.append("requirement_gap")
        if final.segment_coverage < 0.70:
            unresolved_reasons.append("segment_gap")
        if final.verification_required and not final.selected_verified:
            unresolved_reasons.append("verification_incomplete")
        if final.numeric_task and not final.selected_verified:
            unresolved_reasons.append("numeric_verification_incomplete")

        hard_block = bool(
            final.disagreement_count
            or not reply
            or (
                final.verification_required
                and not final.selected_verified
                and not final.selected_grounded
            )
        )
        if hard_block:
            verdict = "BLOCKED"
        elif unresolved_reasons:
            verdict = "PARTIAL"
        else:
            verdict = "OK"

        if verdict != "OK":
            out["needs_teacher"] = bool(
                out.get("needs_teacher")
                or final.needs_teacher
                or hard_block
            )
            if verdict == "BLOCKED":
                try:
                    out["confidence"] = min(float(out.get("confidence", 0.5)), 0.68)
                except (TypeError, ValueError, OverflowError):
                    out["confidence"] = 0.5

        out["reasoning_episode"] = {
            "contract": cls.CONTRACT,
            "verdict": verdict,
            "budget": int(max(0, budget)),
            "attempted_passes": len(rows),
            "accepted_passes": sorted(accepted),
            "unresolved_reasons": list(dict.fromkeys(unresolved_reasons)),
            "phases": [step.to_dict() for step in steps],
            "plan_execute_verify_repair_reverify": True,
            "false_success_guard": True,
        }

        tags = [str(x) for x in out.get("route_tags", [])]
        for tag in (
            "reasoning-episode",
            f"episode-verdict:{verdict.lower()}",
        ):
            if tag not in tags:
                tags.append(tag)
        out["route_tags"] = tags
        return out
