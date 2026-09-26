from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fap_fmg_connectome import FlyConnectomeRouter
from fap_fmg_image_module import (
    FMG_IMAGE_HEIGHT,
    FMG_IMAGE_WIDTH,
    FMGImportedImageModule,
)
from fap_1x_standard_runtime import FAP1xStandardRuntime


class FMGImportTests(unittest.TestCase):
    def test_connectome_routes_available_a1111(self):
        with tempfile.TemporaryDirectory() as tmp:
            router = FlyConnectomeRouter(Path(tmp) / "state.json")
            decision = router.route(
                {
                    "prompt": "cinematic landscape",
                    "steps": 50,
                    "guidance": 9.0,
                },
                {"a1111": True, "diffusers": False},
            )
            self.assertEqual(decision.selected_backend, "a1111")
            self.assertGreater(len(decision.kc_active), 0)

    def test_module_exposes_fmg_fixed_profile_without_network_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = FMGImportedImageModule(
                root=Path(__file__).resolve().parents[1],
                artifact_dir=Path(tmp) / "artifacts",
                image_base="",
            )
            status = module.status()
            self.assertEqual(status["profile"]["width"], FMG_IMAGE_WIDTH)
            self.assertEqual(status["profile"]["height"], FMG_IMAGE_HEIGHT)
            self.assertFalse(status["a1111"]["configured"])
            self.assertTrue(module.matches("幻想都市の画像を生成して"))

    def test_standard_runtime_routes_image_intent_to_fmg_endpoint(self):
        runtime = FAP1xStandardRuntime(root=Path(__file__).resolve().parents[1])
        runtime.fmg_image.generate = lambda text: {
            "ok": True,
            "reply": "FMG test artifact",
            "confidence": 1.0,
            "artifacts": [{"type": "image", "name": "test.png"}],
        }
        result = runtime.run_turn(
            "猫の画像を生成して",
            session_id="fmg-import-test",
        )
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "fmg_image_generation")
        self.assertEqual(result.payload["reply"], "FMG test artifact")
        self.assertEqual(result.payload["artifacts"][0]["type"], "image")


if __name__ == "__main__":
    unittest.main()
