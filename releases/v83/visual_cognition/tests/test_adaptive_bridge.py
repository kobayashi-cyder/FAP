import sys
import unittest
from pathlib import Path

VISUAL_ROOT = Path(__file__).resolve().parents[1]
RELEASES = Path(__file__).resolve().parents[3]
V82_ROOT = RELEASES / "v82" / "adaptive_circuits"
sys.path.insert(0, str(VISUAL_ROOT))
sys.path.insert(0, str(V82_ROOT))

from fap_adaptive_circuits import AdaptiveCircuitController
from fap_visual.adaptive_bridge import VisualAdaptiveCircuitBridge
from fap_visual.skill_graph import VisualSkillGraph


class VisualAdaptiveBridgeTests(unittest.TestCase):
    def test_verified_visual_skill_graph_enters_v82_sparse_registry(self):
        controller = AdaptiveCircuitController(top_k=2)
        graph = VisualSkillGraph()
        bridge = VisualAdaptiveCircuitBridge(graph, controller=controller)
        spec = bridge.register()

        self.assertEqual(spec.circuit_id, "visual_cognition")
        self.assertTrue(controller.verifier.is_eligible(spec))
        self.assertTrue(bridge.routed("画像を描画して"))

    def test_routed_visual_specialist_executes_graph(self):
        controller = AdaptiveCircuitController(top_k=2)
        bridge = VisualAdaptiveCircuitBridge(
            VisualSkillGraph(),
            controller=controller,
        )
        bridge.register()
        result = bridge.execute_if_routed(
            "画像を描画して",
            visual_instruction="canvas=20x20; 赤い円 x=8 y=9 r=3",
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.verified)


if __name__ == "__main__":
    unittest.main()
