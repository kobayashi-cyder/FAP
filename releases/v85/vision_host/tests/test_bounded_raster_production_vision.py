from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V83_ROOT = ROOT.parents[1] / "v83" / "visual_cognition"
sys.path.insert(0, str(V83_ROOT))
sys.path.insert(0, str(ROOT))

from fap_visual.loop import VisualCognitiveLoop
from fap_visual.render import SmallRasterRenderer
from fap_visual.review import VisualDiffer
from fap_visual.visual_ir import VisualIR, VisualPrimitive
from fap_vision_host import (
    ProductionVisionHost,
    build_bounded_raster_backend,
)


class V85BoundedRasterProductionVisionTests(unittest.TestCase):
    def setUp(self):
        backend, observer = build_bounded_raster_backend()
        self.observer = observer
        self.host = ProductionVisionHost(backend)
        self.loop = self.host.build_loop(renderer=SmallRasterRenderer())

    def test_shape_color_and_position_are_observed_from_pixels(self):
        target = VisualIR(
            32,
            32,
            (
                VisualPrimitive(
                    "target-circle",
                    "circle",
                    10,
                    12,
                    9,
                    9,
                    4,
                    (0, 0, 255),
                ),
                VisualPrimitive(
                    "target-rect",
                    "rect",
                    20,
                    4,
                    5,
                    4,
                    0,
                    (255, 0, 0),
                ),
            ),
        )
        frame = SmallRasterRenderer().render(target)
        observed = self.host.probe(frame)

        self.assertEqual(len(observed.primitives), 2)
        circle = next(p for p in observed.primitives if p.kind == "circle")
        rect = next(p for p in observed.primitives if p.kind == "rect")

        self.assertEqual(circle.center, (10.0, 12.0))
        self.assertEqual(circle.radius, 4)
        self.assertEqual(circle.color, (0, 0, 255))
        self.assertEqual((rect.x, rect.y), (20, 4))
        self.assertEqual((rect.width, rect.height), (5, 4))
        self.assertEqual(rect.color, (255, 0, 0))
        self.assertEqual(self.observer.observation_count, 1)

    def test_generated_output_is_reobserved_and_locally_repaired(self):
        target = VisualIR(
            32,
            32,
            (
                VisualPrimitive(
                    "p0",
                    "circle",
                    10,
                    10,
                    7,
                    7,
                    3,
                    (0, 0, 255),
                ),
                VisualPrimitive(
                    "p1",
                    "rect",
                    20,
                    4,
                    5,
                    4,
                    0,
                    (255, 0, 0),
                ),
            ),
        )
        draft = VisualIR(
            32,
            32,
            (
                VisualPrimitive(
                    "p0",
                    "rect",
                    6,
                    7,
                    7,
                    7,
                    0,
                    (0, 180, 0),
                ),
                target.get("p1"),
            ),
        )

        first_frame = SmallRasterRenderer().render(draft)
        first_seen = self.host.probe(first_frame)
        fields = {
            diff.field
            for diff in VisualDiffer().compare(target, first_seen)
            if diff.primitive_id == "p0"
        }
        self.assertTrue({"kind", "color", "position"}.issubset(fields))

        before_loop_count = self.observer.observation_count
        result = self.loop.run(target, draft=draft, max_repairs=2)

        self.assertTrue(result.verified)
        self.assertEqual(len(result.iterations), 2)
        self.assertEqual(
            self.observer.observation_count - before_loop_count,
            len(result.iterations),
        )
        self.assertEqual(result.final_ir.get("p0"), target.get("p0"))
        self.assertEqual(
            result.final_ir.get("p1"),
            target.get("p1"),
            "unaffected primitive must remain unchanged",
        )
        final_diffs = VisualDiffer().compare(target, result.observed)
        self.assertEqual(final_diffs, ())


if __name__ == "__main__":
    unittest.main()
