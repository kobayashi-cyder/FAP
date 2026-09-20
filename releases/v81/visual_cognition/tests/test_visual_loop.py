import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_visual.language import NaturalLanguageVisualPlanner
from fap_visual.loop import VisualCognitiveLoop
from fap_visual.render import SmallRasterRenderer
from fap_visual.review import VisualDiffer
from fap_visual.vision import PrimitiveVision
from fap_visual.visual_ir import MotionPrimitive, VisualIR, VisualPrimitive


class VisualLoopTests(unittest.TestCase):
    def setUp(self):
        self.planner = NaturalLanguageVisualPlanner(default_width=32, default_height=32)
        self.loop = VisualCognitiveLoop(planner=self.planner, renderer=SmallRasterRenderer(), vision=PrimitiveVision())

    def test_language_to_visual_ir_and_roundtrip(self):
        result = self.loop.run_text("canvas=32x32; 赤い円 x=10 y=12 r=4")
        self.assertTrue(result.verified)
        self.assertEqual(result.target.primitives[0].kind, "circle")
        self.assertEqual(result.target.primitives[0].color, (255, 0, 0))
        self.assertEqual(result.observed.primitives[0].center, (10.0, 12.0))
        self.assertEqual(len(result.iterations), 1)

    def test_shape_color_position_are_locally_repaired(self):
        target = VisualIR(32, 32, (
            VisualPrimitive("p0", "circle", 10, 10, 7, 7, 3, (0, 0, 255)),
            VisualPrimitive("p1", "rect", 20, 4, 5, 4, 0, (255, 0, 0)),
        ))
        draft = VisualIR(32, 32, (
            VisualPrimitive("p0", "rect", 6, 7, 7, 7, 0, (0, 180, 0)),
            target.primitives[1],
        ))
        first_frame = self.loop.renderer.render(draft)
        first_seen = self.loop.vision.observe(first_frame)
        fields = {d.field for d in VisualDiffer().compare(target, first_seen) if d.primitive_id == "p0"}
        self.assertTrue({"kind", "color", "position"}.issubset(fields))

        result = self.loop.run(target, draft=draft, max_repairs=2)
        self.assertTrue(result.verified)
        self.assertEqual(result.final_ir.get("p1"), target.get("p1"), "unaffected primitive must remain untouched")
        self.assertEqual(result.final_ir.get("p0"), target.get("p0"))
        self.assertEqual(len(result.iterations), 2)

    def test_rect_size_repair(self):
        target = VisualIR(24, 24, (VisualPrimitive("p0", "rect", 2, 3, 8, 4, 0, (0, 0, 0)),))
        draft = replace(target, primitives=(replace(target.primitives[0], width=3, height=2),))
        result = self.loop.run(target, draft=draft, max_repairs=2)
        self.assertTrue(result.verified)
        self.assertEqual(result.final_ir.get("p0").width, 8)
        self.assertEqual(result.final_ir.get("p0").height, 4)

    def test_motion_is_visual_ir_state_transition(self):
        ir = VisualIR(
            32, 32,
            (VisualPrimitive("p0", "circle", 5, 5, 5, 5, 2, (255, 0, 0)),),
            motions=(MotionPrimitive("p0", "translate", 0.0, 2.0, dx=10, dy=4),),
            duration=2.0,
        )
        mid = ir.sample(1.0)
        end = ir.sample(2.0)
        self.assertEqual((mid.get("p0").x, mid.get("p0").y), (10, 7))
        self.assertEqual((end.get("p0").x, end.get("p0").y), (15, 9))
        self.assertEqual(mid.motions, ())


if __name__ == "__main__":
    unittest.main()
