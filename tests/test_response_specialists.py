from __future__ import annotations

import unittest

from fap_response_specialists import (
    CausalFrameSpecialist,
    CodePlanningSpecialist,
    RequirementCoverageAuditor,
    ResponseAuditor,
    SafeArithmeticSpecialist,
    SegmentCoverageAuditor,
)


class ResponseSpecialistTests(unittest.TestCase):
    def test_arithmetic_is_verified_and_local(self) -> None:
        out = SafeArithmeticSpecialist().run("計算してください: (37+5)*3")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertEqual(out.get("decision_source"), "verified_arithmetic")
        self.assertIn("126", out.get("reply", ""))

    def test_arithmetic_rejects_non_expression(self) -> None:
        self.assertIsNone(SafeArithmeticSpecialist().run("2026年9月26日の話です"))

    def test_causal_frame_does_not_claim_fact_confirmation(self) -> None:
        out = CausalFrameSpecialist().run("なぜこの現象が起きますか？")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("needs_teacher"))
        self.assertFalse(out.get("verified"))
        self.assertIn("反証", out.get("reply", ""))

    def test_code_plan_is_read_only_partial_candidate(self) -> None:
        out = CodePlanningSpecialist().run("C++でJSONを読む関数を実装して。外部ライブラリは使わない")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("code_plan"))
        self.assertTrue(out.get("partial"))
        self.assertTrue(out.get("local"))
        self.assertIn("C++", out.get("reply", ""))

    def test_requirement_coverage_rewards_constraint_mentions(self) -> None:
        audit = RequirementCoverageAuditor()
        request = "C++のみで実装してください。外部ライブラリは使わないでください。"
        strong = audit.score(request, "C++のみで実装し、外部ライブラリは使いません。")
        weak = audit.score(request, "Pythonで実装します。")
        self.assertGreater(strong, weak)

    def test_segment_coverage_rewards_multi_part_answer(self) -> None:
        audit = SegmentCoverageAuditor()
        request = "速度を説明してください。メモリ使用量も説明してください。制約も示してください。"
        broad = audit.score(request, "速度は高速です。メモリ使用量は小さく、制約もあります。")
        narrow = audit.score(request, "速度は高速です。")
        self.assertGreater(broad, narrow)

    def test_response_auditor_stays_bounded(self) -> None:
        result = ResponseAuditor().audit(
            "C++のみで。速度とメモリも説明してください。",
            "C++のみを使います。速度とメモリを説明します。",
        )
        self.assertGreaterEqual(result.combined, 0.0)
        self.assertLessEqual(result.combined, 1.0)


if __name__ == "__main__":
    unittest.main()
