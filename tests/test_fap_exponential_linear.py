from __future__ import annotations

import math
import unittest

from fap_exponential_linear import (
    ExponentialLinearPolicy,
    budget_for_demand,
    estimate_interaction_demand,
)


class ExponentialLinearPolicyTests(unittest.TestCase):
    def test_scale_is_monotonic_and_bounded(self):
        policy = ExponentialLinearPolicy(alpha=2.6, knee=0.55, max_scale=12.0)
        values = [policy.scale(i / 100.0) for i in range(101)]
        self.assertEqual(values[0], 1.0)
        self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))
        self.assertLessEqual(values[-1], 12.0)

    def test_knee_is_value_and_slope_continuous(self):
        policy = ExponentialLinearPolicy(alpha=2.0, knee=0.6, max_scale=100.0)
        eps = 1e-6
        left = policy.scale(policy.knee - eps)
        at = policy.scale(policy.knee)
        right = policy.scale(policy.knee + eps)
        left_slope = (at - left) / eps
        right_slope = (right - at) / eps
        self.assertAlmostEqual(left, at, places=4)
        self.assertAlmostEqual(right, at, places=4)
        self.assertAlmostEqual(left_slope, right_slope, delta=0.02)

    def test_hard_cap_stops_runaway_growth(self):
        policy = ExponentialLinearPolicy(alpha=20.0, knee=0.4, max_scale=3.0)
        self.assertEqual(policy.scale(1.0), 3.0)

    def test_generic_demand_grows_with_request_and_history(self):
        low = estimate_interaction_demand("hello", history_turns=0)
        high = estimate_interaction_demand(
            "\n".join(f"line {i} alpha beta gamma delta" for i in range(120)),
            history_turns=24,
            pressure_hint=1.0,
        )
        self.assertGreater(high.value, low.value)
        self.assertGreater(high.history_component, low.history_component)
        self.assertGreater(high.structure_component, low.structure_component)

    def test_token_component_recognizes_latin_and_japanese_text(self):
        demand = estimate_interaction_demand("alpha beta 日本語 テスト")
        self.assertGreater(demand.token_component, 0.0)
        self.assertGreater(demand.diversity_component, 0.0)

    def test_budget_expands_but_preserves_hard_limits(self):
        low = budget_for_demand(0.0)
        high = budget_for_demand(1.0)
        self.assertGreater(high.route_candidates, low.route_candidates)
        self.assertGreater(high.context_chars, low.context_chars)
        self.assertGreaterEqual(high.reasoning_steps, low.reasoning_steps)
        self.assertLessEqual(high.route_candidates, 32)
        self.assertLessEqual(high.context_chars, 250_000)
        self.assertLessEqual(high.source_bytes, 1_000_000)
        self.assertLessEqual(high.reasoning_steps, 96)
        self.assertLessEqual(high.repair_rounds, 4)
        self.assertLessEqual(high.output_chars, 120_000)

    def test_non_finite_input_is_rejected(self):
        policy = ExponentialLinearPolicy()
        with self.assertRaises(ValueError):
            policy.scale(float("nan"))
        with self.assertRaises(ValueError):
            estimate_interaction_demand("x", pressure_hint=float("inf"))


if __name__ == "__main__":
    unittest.main()
