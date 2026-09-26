from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V83_ROOT = ROOT.parents[1] / "v83" / "visual_cognition"
sys.path.insert(0, str(V83_ROOT))
sys.path.insert(0, str(ROOT))

from fap_visual.render import SmallRasterRenderer
from fap_visual.vision import PrimitiveVision
from fap_visual.visual_ir import VisualIR, VisualPrimitive
from fap_vision_host import (
    ObjectListVisionMapper,
    ProductionVisionHost,
    VisionBackend,
    VisionBackendUnavailable,
    build_bootstrap_visual_loop,
    build_production_visual_loop,
)


class V85ProductionVisionHostTests(unittest.TestCase):
    def test_production_builder_fails_closed_without_backend(self):
        with self.assertRaisesRegex(
            VisionBackendUnavailable,
            "explicitly configured",
        ):
            build_production_visual_loop(None)

    def test_primitive_vision_cannot_be_labeled_production(self):
        primitive = PrimitiveVision()
        backend = VisionBackend(
            "primitive",
            primitive.observe,
            kind="production",
        )
        with self.assertRaisesRegex(
            VisionBackendUnavailable,
            "bootstrap-only",
        ):
            ProductionVisionHost(backend)

    def test_explicit_bootstrap_path_remains_available(self):
        loop = build_bootstrap_visual_loop()
        result = loop.run_text(
            "canvas=16x16; 赤い四角 x=2 y=3 w=4 h=2"
        )
        self.assertTrue(result.verified)

    def test_object_list_mapper_normalizes_existing_vision_output(self):
        frame = SmallRasterRenderer().render(
            VisualIR(
                16,
                16,
                (
                    VisualPrimitive(
                        "p0",
                        "rect",
                        2,
                        3,
                        4,
                        2,
                        0,
                        (255, 0, 0),
                    ),
                ),
            )
        )
        mapper = ObjectListVisionMapper()
        observed = mapper(
            {
                "objects": [
                    {
                        "id": "det:0",
                        "kind": "rect",
                        "x": 2,
                        "y": 3,
                        "w": 4,
                        "h": 2,
                        "rgb": [255, 0, 0],
                    }
                ]
            },
            frame,
        )
        self.assertEqual(observed.primitives[0].center, (3.5, 3.5))
        self.assertEqual(observed.primitives[0].color, (255, 0, 0))

    def test_production_host_drives_v83_feedback_loop(self):
        calls = []

        def existing_vision(frame):
            calls.append((frame.width, frame.height))
            return {
                "objects": [
                    {
                        "kind": "rect",
                        "x": 2,
                        "y": 3,
                        "width": 4,
                        "height": 2,
                        "color": [255, 0, 0],
                    }
                ]
            }

        backend = VisionBackend(
            "existing-vision:test",
            existing_vision,
            mapper=ObjectListVisionMapper(),
        )
        host = ProductionVisionHost(backend)
        loop = host.build_loop()
        result = loop.run_text(
            "canvas=16x16; 赤い四角 x=2 y=3 w=4 h=2"
        )
        self.assertTrue(result.verified)
        self.assertEqual(calls, [(16, 16)])
        manifest = host.manifest()
        self.assertTrue(manifest["production_vision_required"])
        self.assertFalse(manifest["bootstrap_default"])
        self.assertEqual(manifest["backend_id"], "existing-vision:test")

    def test_production_mapper_fails_closed_on_out_of_frame_geometry(self):
        def bad_vision(_frame):
            return {
                "objects": [
                    {
                        "kind": "rect",
                        "x": 15,
                        "y": 15,
                        "w": 4,
                        "h": 4,
                        "rgb": [0, 0, 0],
                    }
                ]
            }

        host = ProductionVisionHost(
            VisionBackend(
                "bad-vision",
                bad_vision,
                mapper=ObjectListVisionMapper(),
            )
        )
        frame = SmallRasterRenderer().render(
            VisualIR(
                16,
                16,
                (
                    VisualPrimitive(
                        "p0",
                        "rect",
                        1,
                        1,
                        2,
                        2,
                        0,
                        (0, 0, 0),
                    ),
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "outside frame"):
            host.probe(frame)

    def test_mapper_accepts_circle_center_radius_contract(self):
        frame = SmallRasterRenderer().render(
            VisualIR(
                20,
                20,
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
                ),
            )
        )
        observed = ObjectListVisionMapper()(
            {
                "objects": [
                    {
                        "kind": "circle",
                        "x": 10,
                        "y": 10,
                        "r": 3,
                        "rgb": [0, 0, 255],
                    }
                ]
            },
            frame,
        )
        self.assertEqual(observed.primitives[0].radius, 3)
        self.assertEqual(observed.primitives[0].center, (10.0, 10.0))


if __name__ == "__main__":
    unittest.main()
