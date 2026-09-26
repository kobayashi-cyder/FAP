from __future__ import annotations

from pathlib import Path
import unittest

from fap_response_redundancy import ResponseRedundancyPlanner
from fap_response_series_executor import ResponseSeriesExecutor


ROOT = Path(__file__).resolve().parents[1]


class ResponseSeriesExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = ResponseRedundancyPlanner()
        self.executor = ResponseSeriesExecutor(ROOT)

    def test_verified_factual_specialist_replaces_weak_primary(self) -> None:
        text = "真空中の光速は何ですか？"
        plan = self.planner.plan(
            text,
            uncertainty=0.8,
            confidence=0.2,
            disagreement=True,
            route_candidates=6,
            verification_depth=5,
            retries=2,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "分からないため確定回答できません。",
                "confidence": 0.2,
                "needs_teacher": True,
            },
            plan,
        )
        self.assertIn("299,792,458", out["reply"])
        execution = out["response_series_execution"]
        self.assertTrue(execution["selection_changed_primary"])
        self.assertIn("factual", execution["consensus_sources"])
        self.assertEqual(execution["executed_lane_votes"], plan.active_lanes)
        self.assertFalse(execution["side_effecting_specialists_executed"])

    def test_unknown_subject_preserves_primary(self) -> None:
        text = "xyzzy_opaque_unknown_subject_7391 について答えて"
        plan = self.planner.plan(text, uncertainty=0.2, confidence=0.85)
        primary = {
            "ok": True,
            "reply": "このローカル知識だけでは確定回答できません。",
            "confidence": 0.7,
            "needs_teacher": True,
        }
        out = self.executor.run(text, [], primary, plan)
        self.assertEqual(out["reply"], primary["reply"])
        self.assertEqual(out["response_series_execution"]["selected"], "primary")

    def test_duplicate_verified_answer_builds_consensus_without_padding(self) -> None:
        text = "プランク定数は何ですか？"
        primary = {
            "ok": True,
            "reply": "プランク定数 h は 6.62607015×10^-34 J·s です。SIでは正確に定義されています。",
            "confidence": 0.99,
            "factual_qa": True,
            "local": True,
        }
        plan = self.planner.plan(text, uncertainty=0.1, confidence=0.99, has_route=True)
        out = self.executor.run(text, [], primary, plan)
        execution = out["response_series_execution"]
        self.assertEqual(execution["selected"], "primary")
        self.assertIn("factual", execution["consensus_sources"])
        self.assertEqual(out["reply"], primary["reply"])

    def test_large_plan_makes_every_planned_lane_vote(self) -> None:
        text = ("前提、反例、制約、代替案、検証方法を分けて考えてください。" * 12)
        plan = self.planner.plan(
            text,
            uncertainty=0.95,
            confidence=0.2,
            disagreement=True,
            counterexample=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
            intent_count=5,
        )
        out = self.executor.run(
            text,
            [],
            {"ok": True, "reply": "暫定回答です。", "confidence": 0.5},
            plan,
        )
        execution = out["response_series_execution"]
        self.assertEqual(plan.active_lanes, 128)
        self.assertEqual(execution["executed_lane_votes"], plan.active_lanes)
        self.assertLessEqual(execution["candidate_count"], 10)
        self.assertGreaterEqual(execution["safe_specialist_calls"], 16)


    def test_verified_arithmetic_specialist_can_replace_weak_primary(self) -> None:
        text = "計算してください: (37+5)*3"
        plan = self.planner.plan(
            text,
            uncertainty=0.8,
            confidence=0.2,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "計算結果を確定できません。",
                "confidence": 0.2,
                "needs_teacher": True,
            },
            plan,
        )
        self.assertIn("126", out["reply"])
        execution = out["response_series_execution"]
        self.assertTrue(execution["selection_changed_primary"])
        self.assertIn("arithmetic", execution["consensus_sources"])

    def test_candidate_metadata_contains_coverage_audits(self) -> None:
        text = "速度を説明してください。制約も説明してください。"
        plan = self.planner.plan(text, uncertainty=0.5, confidence=0.6)
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "速度と制約について説明します。",
                "confidence": 0.7,
            },
            plan,
        )
        rows = out["response_series_execution"]["candidates"]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("requirement_coverage", row)
            self.assertIn("segment_coverage", row)

    def test_verified_linear_equation_can_replace_weak_primary(self) -> None:
        text = "方程式 2x + 3 = 11 を解いて"
        plan = self.planner.plan(
            text,
            uncertainty=0.9,
            confidence=0.2,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "方程式を解けません。",
                "confidence": 0.2,
                "needs_teacher": True,
            },
            plan,
        )
        self.assertIn("x = 4", out["reply"])
        self.assertTrue(out["response_series_execution"]["selection_changed_primary"])
        self.assertIn("linear_equation", out["response_series_execution"]["consensus_sources"])

    def test_exact_linear_specialist_wins_zero_solution(self) -> None:
        text = "方程式 6x - 1 = -1 を解いて"
        plan = self.planner.plan(
            text,
            uncertainty=0.9,
            confidence=0.2,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "-1 = -1",
                "confidence": 0.99,
                "verified": True,
                "grounded": True,
            },
            plan,
        )
        self.assertIn("x = 0", out["reply"])
        self.assertIn(
            "linear_equation",
            out["response_series_execution"]["consensus_sources"],
        )

    def test_multi_intent_composition_beats_partial_exact_answer(self) -> None:
        text = "方程式 2x + 3 = 11 を解いて。エントロピーについて説明して。"
        plan = self.planner.plan(
            text,
            uncertainty=0.95,
            confidence=0.2,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
            intent_count=2,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "x = 4 です。",
                "confidence": 0.99,
                "verified": True,
                "grounded": True,
            },
            plan,
        )
        self.assertIn("x = 4", out["reply"])
        self.assertIn("エントロピー", out["reply"])
        execution = out["response_series_execution"]
        self.assertEqual(execution["selected"], "subproblem")
        self.assertIn("subproblem", execution["consensus_sources"])

    def test_partial_exact_solver_does_not_take_over_multi_intent_request(self) -> None:
        text = "方程式 2x + 3 = 11 を解いて。ZXQV-UNKNOWN-93について説明して。"
        plan = self.planner.plan(
            text,
            uncertainty=0.95,
            confidence=0.4,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
            intent_count=2,
        )
        primary = {
            "ok": True,
            "reply": "後半はローカル知識では確認できません。",
            "confidence": 0.66,
            "grounded": True,
            "needs_teacher": True,
        }
        out = self.executor.run(text, [], primary, plan)
        self.assertNotEqual(
            out["response_series_execution"]["selected"],
            "linear_equation",
        )
        self.assertIn("後半", out["reply"])

    def test_verified_physics_numeric_can_replace_weak_primary(self) -> None:
        text = "質量=2 kg、加速度=3 m/s^2 のとき力を求めて"
        plan = self.planner.plan(
            text,
            uncertainty=0.9,
            confidence=0.2,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "物理計算を確定できません。",
                "confidence": 0.2,
                "needs_teacher": True,
            },
            plan,
        )
        self.assertIn("6", out["reply"])
        self.assertTrue(out["response_series_execution"]["selection_changed_primary"])
        self.assertIn("physics_numeric", out["response_series_execution"]["consensus_sources"])


    def test_multi_step_math_explorer_participates_in_128_lane_vote(self) -> None:
        text = "計算: 2+3 と 4*5 をそれぞれ求めて"
        plan = self.planner.plan(
            text,
            uncertainty=0.95,
            confidence=0.2,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
        )
        out = self.executor.run(
            text,
            [],
            {
                "ok": True,
                "reply": "複数の計算を確定できません。",
                "confidence": 0.2,
                "needs_teacher": True,
            },
            plan,
        )
        execution = out["response_series_execution"]
        diagnostics = {row["source"]: row["state"] for row in execution["specialist_diagnostics"]}
        self.assertGreaterEqual(plan.active_lanes, 96)
        self.assertEqual(diagnostics.get("multi_step_math"), "candidate")
        self.assertEqual(execution["executed_lane_votes"], plan.active_lanes)

    def test_longform_contradiction_explorer_participates(self) -> None:
        text = "mode=disabled"
        history = [{"role": "user", "text": "mode=enabled"}]
        plan = self.planner.plan(
            text,
            uncertainty=0.9,
            confidence=0.25,
            disagreement=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
        )
        out = self.executor.run(
            text,
            history,
            {
                "ok": True,
                "reply": "設定はそのままです。",
                "confidence": 0.3,
                "needs_teacher": True,
            },
            plan,
        )
        diagnostics = {
            row["source"]: row["state"]
            for row in out["response_series_execution"]["specialist_diagnostics"]
        }
        self.assertEqual(diagnostics.get("longform_contradiction"), "candidate")
        self.assertIn("mode", out["reply"])

if __name__ == "__main__":
    unittest.main()
