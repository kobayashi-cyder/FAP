from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT.parents[1]
V79 = RELEASES / "v79" / "creativity_engine"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V79))

from fap_adaptive_circuits import PrimitiveCircuitBridge
from fap_creativity import (
    Instruction,
    MiniIRSandbox,
    PrimitiveInventor,
    PrimitivePromotionLoop,
    PrimitiveTestCase,
)


class PrimitiveCircuitBridgeTests(unittest.TestCase):
    def make_active_loop(self):
        sandbox = MiniIRSandbox(timeout_ms=50)
        inventor = PrimitiveInventor(sandbox)
        candidate = inventor.compose(
            name="normalize_text",
            input_kind="string",
            program=[Instruction("strip"), Instruction("lower")],
            tests=[
                PrimitiveTestCase(" A ", "a"),
                PrimitiveTestCase("B", "b"),
                PrimitiveTestCase(" C", "c"),
                PrimitiveTestCase("D ", "d"),
                PrimitiveTestCase("   ", "", boundary=True),
            ],
            description="normalize text with strip and lower",
        )
        loop = PrimitivePromotionLoop(sandbox=sandbox)
        decision = loop.evaluate(
            candidate,
            shadow_cases=[
                PrimitiveTestCase(" E ", "e"),
                PrimitiveTestCase("F ", "f"),
                PrimitiveTestCase(" G", "g"),
            ],
        )
        self.assertTrue(decision.promoted)
        return loop, candidate

    def test_only_active_primitive_is_adopted_and_certified(self):
        loop, candidate = self.make_active_loop()
        bridge = PrimitiveCircuitBridge(loop)
        adopted = bridge.sync_active()
        self.assertEqual(adopted, [candidate.primitive_id])
        spec = bridge.controller.registry.get(candidate.primitive_id)
        self.assertTrue(spec.verified)
        self.assertEqual(spec.stage, "consolidated")

    def test_shadow_primitive_is_not_routable(self):
        sandbox = MiniIRSandbox(timeout_ms=50)
        inventor = PrimitiveInventor(sandbox)
        candidate = inventor.compose(
            name="absolute",
            input_kind="number",
            program=[Instruction("abs")],
            tests=[
                PrimitiveTestCase(-2, 2),
                PrimitiveTestCase(-1, 1),
                PrimitiveTestCase(0, 0, boundary=True),
                PrimitiveTestCase(1, 1),
                PrimitiveTestCase(2, 2),
            ],
        )
        loop = PrimitivePromotionLoop(sandbox=sandbox)
        decision = loop.evaluate(candidate, shadow_cases=[PrimitiveTestCase(-5, 5)])
        self.assertEqual(decision.stage, "shadow")
        bridge = PrimitiveCircuitBridge(loop)
        self.assertEqual(bridge.sync_active(), [])
        self.assertEqual(bridge.route("absolute number").circuit_ids, ())

    def test_sparse_route_executes_active_primitive(self):
        loop, candidate = self.make_active_loop()
        bridge = PrimitiveCircuitBridge(loop, top_k=1)
        decision, results = bridge.execute("normalize text strip lower", "  HELLO  ", top_k=1)
        self.assertEqual(decision.circuit_ids, (candidate.primitive_id,))
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].output, "hello")
        self.assertTrue(bridge.observe(decision, results, evidence_id="runtime-ok"))
        self.assertIn(candidate.primitive_id, bridge.controller.memory.entries)

    def test_failed_runtime_does_not_enter_active_memory(self):
        loop, candidate = self.make_active_loop()
        bridge = PrimitiveCircuitBridge(loop, top_k=1)
        decision = bridge.route("normalize text strip lower", top_k=1)
        self.assertEqual(decision.circuit_ids, (candidate.primitive_id,))
        _, results = bridge.execute("normalize text strip lower", 123, top_k=1)
        self.assertFalse(results[0].ok)
        self.assertFalse(bridge.observe(decision, results, evidence_id="runtime-bad"))
        self.assertNotIn(candidate.primitive_id, bridge.controller.memory.entries)


if __name__ == "__main__":
    unittest.main()
