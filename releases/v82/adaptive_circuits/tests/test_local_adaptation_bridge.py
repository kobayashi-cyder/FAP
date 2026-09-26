from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT.parents[1]
V81 = RELEASES / "v81" / "local_adaptation"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V81))

from fap_adaptive_circuits import (
    AdaptiveCircuitController,
    LocalAdaptationCircuitBridge,
    LOCAL_ADAPTATION_CIRCUIT_ID,
)
from fap_local_adaptation import LocalAdaptiveCore


class LocalAdaptationCircuitBridgeTests(unittest.TestCase):
    def test_register_is_verifier_gated_and_does_not_train(self):
        core = LocalAdaptiveCore()
        before = core.export_state()
        bridge = LocalAdaptationCircuitBridge(core)
        self.assertTrue(bridge.register())
        after = core.export_state()
        self.assertEqual(before["readout"], after["readout"])
        self.assertEqual(before["seen_learning_evidence"], after["seen_learning_evidence"])
        spec = bridge.controller.registry.get(LOCAL_ADAPTATION_CIRCUIT_ID)
        self.assertTrue(spec.verified)
        self.assertEqual(spec.stage, "consolidated")

    def test_irrelevant_task_can_activate_zero_local_circuits(self):
        core = LocalAdaptiveCore()
        controller = AdaptiveCircuitController(top_k=2, activation_threshold=0.31)
        bridge = LocalAdaptationCircuitBridge(core, controller=controller)
        self.assertEqual(bridge.guidance_if_routed("天気の単純な挨拶"), "")

    def test_predictive_task_routes_local_adaptation(self):
        core = LocalAdaptiveCore()
        bridge = LocalAdaptationCircuitBridge(core, top_k=2)
        guidance = bridge.guidance_if_routed("次入力を予測して失敗パターンを回避する")
        self.assertIn("[FAP local-adaptation guidance]", guidance)

    def test_verified_success_enters_v82_active_memory(self):
        core = LocalAdaptiveCore()
        bridge = LocalAdaptationCircuitBridge(core, top_k=2)
        self.assertTrue(bridge.register())
        result = bridge.learn_transition(
            source_text="次入力を予測する局所学習",
            target_text="予測成功",
            evidence_id="v82-local-success-1",
            verified=True,
            success=True,
            action_tag="predictive",
        )
        self.assertTrue(result.learned)
        self.assertIn(LOCAL_ADAPTATION_CIRCUIT_ID, bridge.controller.memory.entries)


if __name__ == "__main__":
    unittest.main()
