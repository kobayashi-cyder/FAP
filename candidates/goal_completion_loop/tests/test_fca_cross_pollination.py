from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop import (
    CapabilityBid,
    SparseCapabilityGate,
    StructuredPlannerAdapter,
    GoalSpec,
    GoalState,
)


class FCACrossPollinationTests(unittest.TestCase):
    def test_sparse_gate_selects_under_budget(self):
        gate = SparseCapabilityGate(budget=1.0, max_active=2)
        selected = gate.select(
            [
                CapabilityBid("verify", 1.0, 0.8, 0.4, 0.4),
                CapabilityBid("search", 0.9, 0.5, 0.7, 0.5),
                CapabilityBid("media", 0.2, 0.2, 0.1, 0.8),
            ],
            {"verify", "search", "media"},
        )
        self.assertEqual(set(selected), {"verify", "search"})

    def test_planner_only_sees_sparse_active_capabilities(self):
        seen = {}

        def model(payload):
            seen["capabilities"] = payload["capabilities"]
            return {"actions": [{"kind": "verify", "instruction": "verify result"}]}

        gate = SparseCapabilityGate(budget=0.6, max_active=1)
        selector = gate.as_selector(
            lambda goal, state, available: [
                CapabilityBid("verify", 1.0, 1.0, 0.5, 0.4),
                CapabilityBid("media", 0.1, 0.1, 0.0, 0.5),
            ]
        )
        planner = StructuredPlannerAdapter(
            model,
            capabilities={"verify", "media"},
            capability_selector=selector,
        )
        goal = GoalSpec("g", "finish")
        actions = planner.plan(goal, GoalState(goal))
        self.assertEqual(seen["capabilities"], ["verify"])
        self.assertEqual(actions[0].kind, "verify")

    def test_filtered_capability_is_rejected(self):
        def model(_payload):
            return {"actions": [{"kind": "media", "instruction": "generate"}]}

        gate = SparseCapabilityGate(budget=0.6, max_active=1)
        selector = gate.as_selector(
            lambda goal, state, available: [
                CapabilityBid("verify", 1.0, 1.0, 0.5, 0.4),
                CapabilityBid("media", 0.0, 0.0, 0.0, 0.5),
            ]
        )
        planner = StructuredPlannerAdapter(
            model,
            capabilities={"verify", "media"},
            capability_selector=selector,
        )
        goal = GoalSpec("g", "finish")
        with self.assertRaises(ValueError):
            planner.plan(goal, GoalState(goal))


if __name__ == "__main__":
    unittest.main()
