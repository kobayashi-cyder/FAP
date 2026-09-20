import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_visual.skill_graph import VisualSkillGraph


class VisualSkillGraphTests(unittest.TestCase):
    def test_feedback_cycle_is_integrated_and_active(self):
        graph = VisualSkillGraph()
        manifest = graph.manifest()
        self.assertEqual(manifest["state_space"], "VisualIR")
        self.assertTrue(manifest["vision_feedback_required"])
        self.assertFalse(manifest["external_diffusion_required"])
        self.assertEqual({n["name"] for n in manifest["nodes"]}, {"imagine", "draw", "see", "review", "repair", "motion"})
        edges = {(e["source"], e["target"]) for e in manifest["edges"]}
        self.assertIn(("draw", "see"), edges)
        self.assertIn(("repair", "draw"), edges)

    def test_graph_executes_verified_visual_cycle(self):
        graph = VisualSkillGraph()
        result = graph.execute_text("canvas=24x24; 青い四角 x=3 y=4 w=6 h=5")
        self.assertTrue(result.verified)
        self.assertEqual(result.observed.primitives[0].color, (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
