from __future__ import annotations

import unittest

from fap_adaptive_reasoning import AdaptiveReasoningGovernor


class AdaptiveReasoningGovernorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.governor = AdaptiveReasoningGovernor()

    def test_strong_verified_answer_does_not_escalate(self):
        payload = {
            "reply": "真空中の光速は 299,792,458 m/s です。",
            "confidence": 0.99,
            "factual_qa": True,
            "grounded": True,
            "response_series_execution": {
                "selected": "primary",
                "candidate_count": 2,
                "verified_disagreements": [],
                "candidates": [
                    {
                        "id": "primary",
                        "confidence": 0.99,
                        "verified": True,
                        "grounded": True,
                        "needs_teacher": False,
                        "requirement_coverage": 1.0,
                        "segment_coverage": 1.0,
                    }
                ],
            },
        }
        assessment = self.governor.assess("真空中の光速は？", payload)
        self.assertEqual(assessment.escalation_level, 0)
        self.assertTrue(assessment.selected_verified)
        self.assertLess(assessment.epistemic_risk, 0.20)

    def test_low_confidence_disagreement_escalates_to_max(self):
        payload = {
            "reply": "暫定回答です。",
            "confidence": 0.35,
            "needs_teacher": True,
            "response_series_execution": {
                "selected": "primary",
                "candidate_count": 5,
                "verified_disagreements": [["a", "b"]],
                "candidates": [
                    {
                        "id": "primary",
                        "confidence": 0.35,
                        "verified": False,
                        "grounded": False,
                        "needs_teacher": True,
                        "requirement_coverage": 0.55,
                        "segment_coverage": 0.60,
                    }
                ],
            },
        }
        assessment = self.governor.assess(
            "前提、反例、制約を比較し、検証して結論を出してください。",
            payload,
        )
        self.assertEqual(assessment.escalation_level, 2)
        self.assertIn("verified_disagreement", assessment.reasons)
        plan = self.governor.escalation_plan_kwargs(assessment, 2)
        self.assertEqual(plan["route_candidates"], 8)
        self.assertEqual(plan["verification_depth"], 6)
        self.assertTrue(plan["counterexample"])

    def test_unverified_numeric_claim_always_gets_verification_pass(self):
        payload = {
            "reply": "答えは 126 です。",
            "confidence": 0.92,
            "grounded": False,
            "response_series_execution": {
                "selected": "primary",
                "candidate_count": 1,
                "verified_disagreements": [],
                "candidates": [
                    {
                        "id": "primary",
                        "confidence": 0.92,
                        "verified": False,
                        "grounded": False,
                        "needs_teacher": False,
                        "requirement_coverage": 1.0,
                        "segment_coverage": 1.0,
                    }
                ],
            },
        }
        assessment = self.governor.assess("計算してください: (37+5)*3", payload)
        self.assertGreaterEqual(assessment.escalation_level, 1)
        self.assertIn("numeric_unverified", assessment.reasons)

    def test_fresh_ungrounded_claim_escalates(self):
        payload = {
            "reply": "現在の価格は100です。",
            "confidence": 0.9,
            "grounded": False,
            "response_series_execution": {
                "selected": "primary",
                "candidate_count": 1,
                "verified_disagreements": [],
                "candidates": [
                    {
                        "id": "primary",
                        "confidence": 0.9,
                        "verified": False,
                        "grounded": False,
                        "needs_teacher": False,
                        "requirement_coverage": 1.0,
                        "segment_coverage": 1.0,
                    }
                ],
            },
        }
        assessment = self.governor.assess("現在の価格は？", payload)
        self.assertGreaterEqual(assessment.escalation_level, 1)
        self.assertTrue(assessment.freshness_required)

    def test_calibration_caps_unverified_high_risk_confidence(self):
        payload = {
            "reply": "たぶんこの数値です。",
            "confidence": 0.98,
            "needs_teacher": True,
            "response_series_execution": {
                "selected": "primary",
                "candidate_count": 1,
                "verified_disagreements": [],
                "candidates": [
                    {
                        "id": "primary",
                        "confidence": 0.98,
                        "verified": False,
                        "grounded": False,
                        "needs_teacher": True,
                        "requirement_coverage": 0.7,
                        "segment_coverage": 0.7,
                    }
                ],
            },
        }
        assessment = self.governor.assess("厳密に検証して答えて", payload)
        out = self.governor.calibrate(
            "厳密に検証して答えて",
            payload,
            dispatch_state="handled",
            passes=2,
            assessments=[assessment],
        )
        self.assertLessEqual(out["confidence"], 0.62)
        self.assertTrue(out["needs_teacher"])
        self.assertTrue(out["reasoning_governor"]["fail_closed"])
        self.assertEqual(out["reasoning_governor"]["passes"], 2)


if __name__ == "__main__":
    unittest.main()
