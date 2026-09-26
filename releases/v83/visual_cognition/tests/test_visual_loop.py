import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_visual.loop import VisualCognitiveLoop
from fap_visual.render import SmallRasterRenderer
from fap_visual.review import VisualDiffer
from fap_visual.vision import CallableVisionAdapter, PrimitiveVision
from fap_visual.visual_ir import MotionPrimitive, VisualIR, VisualPrimitive


class CountingVision:
    def __init__(self):
        self.count = 0
        self.inner = PrimitiveVision()

    def observe(self, frame):
        self.count += 1
        return self.inner.observe(frame)


class VisualLoopTests(unittest.TestCase):
    def setUp(self):
        self.loop = VisualCognitiveLoop(
            renderer=SmallRasterRenderer(),
            vision=PrimitiveVision(),
        )

    def test_language_to_visual_ir_and_vision_roundtrip(self):
        result = self.loop.run_text("canvas=32x32; 赤い円 x=10 y=12 r=4")
        self.assertTrue(result.verified)
        self.assertEqual(result.target.primitives[0].kind, "circle")
        self.assertEqual(result.target.primitives[0].color, (255, 0, 0))
        self.assertEqual(result.observed.primitives[0].center, (10.0, 12.0))
        self.assertEqual(len(result.iterations), 1)

    def test_shape_color_position_are_structured_and_locally_repaired(self):
        target = VisualIR(32, 32, (
            VisualPrimitive("p0", "circle", 10, 10, 7, 7, 3, (0, 0, 255)),
            VisualPrimitive("p1", "rect", 20, 4, 5, 4, 0, (255, 0, 0)),
        ))
        draft = VisualIR(32, 32, (
            VisualPrimitive("p0", "rect", 6, 7, 7, 7, 0, (0, 180, 0)),
            target.primitives[1],
        ))

        first_seen = self.loop.vision.observe(self.loop.renderer.render(draft))
        fields = {
            diff.field
            for diff in VisualDiffer().compare(target, first_seen)
            if diff.primitive_id == "p0"
        }
        self.assertTrue({"kind", "color", "position"}.issubset(fields))

        result = self.loop.run(target, draft=draft, max_repairs=2)
        self.assertTrue(result.verified)
        self.assertEqual(result.final_ir.get("p0"), target.get("p0"))
        self.assertEqual(
            result.final_ir.get("p1"),
            target.get("p1"),
            "unaffected primitive must not be rewritten",
        )
        self.assertEqual(len(result.iterations), 2)

    def test_every_candidate_is_returned_through_vision(self):
        vision = CountingVision()
        loop = VisualCognitiveLoop(renderer=SmallRasterRenderer(), vision=vision)
        target = VisualIR(
            24, 24,
            (VisualPrimitive("p0", "rect", 2, 3, 8, 4, 0, (0, 0, 0)),),
        )
        draft = replace(
            target,
            primitives=(replace(target.primitives[0], width=3, height=2),),
        )
        result = loop.run(target, draft=draft, max_repairs=2)
        self.assertTrue(result.verified)
        self.assertEqual(vision.count, len(result.iterations))
        self.assertEqual(vision.count, 2)

    def test_motion_is_visual_ir_state_transition(self):
        ir = VisualIR(
            32, 32,
            (VisualPrimitive("p0", "circle", 5, 5, 5, 5, 2, (255, 0, 0)),),
            motions=(
                MotionPrimitive("p0", "translate", 0.0, 2.0, dx=10, dy=4),
            ),
            duration=2.0,
        )
        mid = ir.sample(1.0)
        end = ir.sample(2.0)
        self.assertEqual((mid.get("p0").x, mid.get("p0").y), (10, 7))
        self.assertEqual((end.get("p0").x, end.get("p0").y), (15, 9))
        self.assertEqual(mid.motions, ())

    def test_existing_vision_output_can_be_normalized_to_visual_ir(self):
        frame = SmallRasterRenderer().render(
            VisualIR(
                12, 12,
                (VisualPrimitive("p0", "rect", 2, 3, 4, 2, 0, (255, 0, 0)),),
            )
        )

        def existing_vision(_frame):
            return {
                "objects": [
                    {"kind": "rect", "x": 2, "y": 3, "w": 4, "h": 2, "rgb": [255, 0, 0]}
                ]
            }

        def to_ir(raw, source_frame):
            obj = raw["objects"][0]
            return VisualIR(
                source_frame.width,
                source_frame.height,
                (
                    VisualPrimitive(
                        "vision:0",
                        obj["kind"],
                        obj["x"],
                        obj["y"],
                        obj["w"],
                        obj["h"],
                        0,
                        tuple(obj["rgb"]),
                    ),
                ),
                source_frame.background,
            )

        adapter = CallableVisionAdapter(existing_vision, mapper=to_ir)
        observed = adapter.observe(frame)
        self.assertEqual(observed.primitives[0].color, (255, 0, 0))
        self.assertEqual(observed.primitives[0].center, (3.5, 3.5))


if __name__ == "__main__":
    unittest.main()
