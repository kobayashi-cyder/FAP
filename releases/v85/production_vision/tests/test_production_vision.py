from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
V83_ROOT = ROOT.parents[1] / "v83" / "visual_cognition"
sys.path.insert(0, str(V83_ROOT))
sys.path.insert(0, str(ROOT))

from fap_production_vision import build_production_visual_runtime
from fap_visual import PrimitiveVision, VisualIR, VisualPrimitive


class V85ProductionVisionTests(unittest.TestCase):
    def target(self):
        return VisualIR(
            16,
            16,
            (
                VisualPrimitive(
                    "r1",
                    "rect",
                    2,
                    3,
                    width=5,
                    height=4,
                    color=(12, 34, 56),
                ),
            ),
        )

    def test_production_runtime_fails_closed_without_vision(self):
        with self.assertRaisesRegex(ValueError, "production vision callback"):
            build_production_visual_runtime()

    def test_external_callback_is_wired_through_callable_adapter(self):
        calls = []

        def existing_vision(frame):
            calls.append((frame.width, frame.height))
            return PrimitiveVision().observe(frame)

        runtime = build_production_visual_runtime(
            vision_callback=existing_vision,
            vision_name="existing-host-vision",
        )
        result = runtime.execute_ir(self.target())
        self.assertTrue(result.verified)
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(type(runtime.vision).__name__, "CallableVisionAdapter")

    def test_raw_existing_vision_output_uses_mapper(self):
        seen = []

        def existing_vision(frame):
            observed = PrimitiveVision().observe(frame)
            seen.append(observed)
            return {"observation": observed}

        def mapper(raw, frame):
            self.assertEqual(frame.width, 16)
            return raw["observation"]

        runtime = build_production_visual_runtime(
            vision_callback=existing_vision,
            vision_mapper=mapper,
            vision_name="mapped-host-vision",
        )
        result = runtime.execute_ir(self.target())
        self.assertTrue(result.verified)
        self.assertTrue(seen)

    def test_invalid_mapped_output_fails_closed(self):
        runtime = build_production_visual_runtime(
            vision_callback=lambda frame: {"bad": True},
            vision_mapper=lambda raw, frame: raw,
        )
        with self.assertRaisesRegex(TypeError, "return VisualIR"):
            runtime.execute_ir(self.target())

    def test_manifest_disables_bootstrap_fallback(self):
        runtime = build_production_visual_runtime(
            vision_callback=lambda frame: PrimitiveVision().observe(frame),
            vision_name="prod",
        )
        manifest = runtime.manifest()
        self.assertEqual(manifest["adapter"], "CallableVisionAdapter")
        self.assertTrue(manifest["requires_external_vision"])
        self.assertFalse(manifest["primitive_vision_fallback"])
        self.assertTrue(manifest["vision_feedback_required"])
        self.assertEqual(manifest["shared_state"], "VisualIR")

    def test_existing_vision_still_participates_after_repair(self):
        calls = []
        primitive = PrimitiveVision()

        def existing_vision(frame):
            calls.append(frame)
            observed = primitive.observe(frame)
            if len(calls) == 1:
                p = observed.primitives[0]
                shifted = VisualPrimitive(
                    p.primitive_id,
                    p.kind,
                    p.x + 1,
                    p.y,
                    p.width,
                    p.height,
                    p.radius,
                    p.color,
                )
                return VisualIR(
                    observed.width,
                    observed.height,
                    (shifted,),
                    observed.background,
                )
            return observed

        runtime = build_production_visual_runtime(
            vision_callback=existing_vision,
        )
        result = runtime.execute_ir(self.target(), max_repairs=2)
        self.assertTrue(result.verified)
        self.assertGreaterEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
