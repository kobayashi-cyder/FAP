from __future__ import annotations

import unittest

from fap_adaptive_reasoning import ReasoningAssessment
from fap_reasoning_episode import ReasoningEpisodeController


def assessment(
    *,
    confidence: float = 0.9,
    risk: float = 0.1,
    verified: bool = True,
    grounded: bool = True,
    requirement: float = 1.0,
    segment: float = 1.0,
    disagreements: int = 0,
    needs_teacher: bool = False,
    escalation: int = 0,
    verification_required: bool = False,
    numeric: bool = False,
    reasons: tuple[str, ...] = (),
) -> ReasoningAssessment:
    return ReasoningAssessment(
        contract="fap.reasoning.governor.v1",
        complexity=0.5,
        epistemic_risk=risk,
        confidence=confidence,
        requirement_coverage=requirement,
        segment_coverage=segment,
        selected_verified=verified,
        selected_grounded=grounded,
        needs_teacher=needs_teacher,
        disagreement_count=disagreements,
        candidate_count=3,
        intent_count=1,
        freshness_required=False,
        verification_required=verification_required,
        numeric_task=numeric,
        escalation_level=escalation,
        reasons=reasons,
    )


class ReasoningEpisodeControllerTests(unittest.TestCase):
    def test_strong_answer_uses_no_repair_budget(self):
        row = assessment()
        self.assertEqual(
            ReasoningEpisodeController.escalation_budget(row),
            0,
        )

    def test_repairable_conflict_gets_reverify_pass(self):
        row = assessment(
            confidence=0.4,
            risk=0.7,
            verified=False,
            grounded=False,
            disagreements=1,
            escalation=2,
            reasons=("verified_disagreement",),
        )
        self.assertEqual(
            ReasoningEpisodeController.escalation_budget(row),
            3,
        )
        self.assertEqual(
            ReasoningEpisodeController.phase_for_pass(3, 3),
            "reverify",
        )

    def test_external_only_gap_does_not_waste_third_local_pass(self):
        row = assessment(
            confidence=0.4,
            risk=0.7,
            verified=False,
            grounded=False,
            needs_teacher=True,
            escalation=2,
            reasons=("needs_external_knowledge",),
        )
        self.assertEqual(
            ReasoningEpisodeController.escalation_budget(row),
            2,
        )

    def test_unresolved_verified_conflict_cannot_be_clean_success(self):
        row = assessment(
            confidence=0.9,
            risk=0.7,
            verified=True,
            grounded=True,
            disagreements=1,
            escalation=2,
            reasons=("verified_disagreement",),
        )
        out = ReasoningEpisodeController.finalize(
            {"reply": "競合候補があります。", "confidence": 0.95},
            [row],
            accepted_passes=[0],
            budget=3,
            final_assessment=row,
        )
        episode = out["reasoning_episode"]
        self.assertEqual(episode["verdict"], "BLOCKED")
        self.assertTrue(out["needs_teacher"])
        self.assertLessEqual(out["confidence"], 0.68)

    def test_rejected_last_attempt_does_not_poison_final_verdict(self):
        good = assessment()
        rejected = assessment(
            confidence=0.3,
            risk=0.8,
            verified=False,
            grounded=False,
            requirement=0.4,
            segment=0.4,
            escalation=2,
            reasons=("requirement_gap", "segment_gap"),
        )
        out = ReasoningEpisodeController.finalize(
            {"reply": "検証済み回答", "confidence": 0.9},
            [good, rejected],
            accepted_passes=[0],
            budget=1,
            final_assessment=good,
        )
        episode = out["reasoning_episode"]
        self.assertEqual(episode["verdict"], "OK")
        self.assertTrue(episode["final_from_accepted_candidate"])
        self.assertEqual(episode["accepted_passes"], [0])


if __name__ == "__main__":
    unittest.main()
