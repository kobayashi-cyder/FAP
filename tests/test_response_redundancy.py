from __future__ import annotations

import unittest

from fap_response_redundancy import ResponseRedundancyPlanner


class ResponseRedundancyTests(unittest.TestCase):
    def test_normal_turn_keeps_bounded_redundancy(self) -> None:
        planner = ResponseRedundancyPlanner()
        plan = planner.plan(
            "この仕組みを説明してください。",
            uncertainty=0.10,
            confidence=0.90,
            has_route=True,
        )
        self.assertGreaterEqual(plan.active_lanes, 6)
        self.assertLessEqual(plan.active_lanes, 16)
        self.assertLess(plan.coverage_target, 1.0)
        self.assertTrue(plan.partial_coverage_allowed)

    def test_hard_turn_expands_to_large_response_scale(self) -> None:
        planner = ResponseRedundancyPlanner()
        text = (
            "前提を分解し、複数の説明、反例、制約、代替案、検証方法を考えてください。"
            "不確実な箇所は明示し、長期的な影響と実装上の問題も別々に検討してください。"
        ) * 8
        plan = planner.plan(
            text,
            uncertainty=0.90,
            confidence=0.30,
            disagreement=True,
            counterexample=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
            intent_count=5,
            has_route=False,
        )
        self.assertGreaterEqual(plan.active_lanes, 48)
        self.assertLessEqual(plan.active_lanes, planner.MAX_LANES)
        self.assertGreaterEqual(plan.synthesis_width, 6)
        self.assertLessEqual(plan.synthesis_width, planner.MAX_SYNTHESIS)
        self.assertGreaterEqual(len({x.role for x in plan.lanes}), 16)
        self.assertLessEqual(plan.coverage_target, 0.90)

    def test_lane_ids_are_unique_even_after_role_reuse(self) -> None:
        planner = ResponseRedundancyPlanner()
        plan = planner.plan(
            "x" * 2000,
            uncertainty=1.0,
            confidence=0.0,
            disagreement=True,
            counterexample=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
            intent_count=8,
        )
        ids = [x.lane_id for x in plan.lanes]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
