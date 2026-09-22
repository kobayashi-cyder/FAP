from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import fap_semantic_action_router as semantic_action_module
from fap_semantic_action_router import SemanticActionRouter
from fap_v87_62_semantic_action_gateway import FAPV8762Unified


class SemanticActionRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.router = SemanticActionRouter(cls.root)

    def test_create_paraphrases_share_image_generation_route(self):
        prompts = [
            "犬の絵を作成して",
            "猫の画像を生成して",
            "風景写真を作って",
            "an illustration of a tree, please create it",
        ]
        for prompt in prompts:
            match = self.router.match(prompt)
            self.assertIsNotNone(match, prompt)
            self.assertEqual(match["resource_id"], "image")
            self.assertEqual(match["action_id"], "create")
            self.assertEqual(match["route"], "image_generate")

    def test_capability_is_separate_action(self):
        match = self.router.match("画像生成はできますか？")
        self.assertIsNotNone(match)
        self.assertEqual(match["resource_id"], "image")
        self.assertEqual(match["action_id"], "capability")
        self.assertEqual(match["route"], "image_capability")

    def test_router_source_has_no_subject_specific_branch(self):
        source = inspect.getsource(semantic_action_module)
        for forbidden in ("犬", "猫", "beagle", "dog", "cat"):
            self.assertNotIn(forbidden, source)

    def test_latest_chat_routes_screenshot_phrase_to_image_organ(self):
        core = FAPV8762Unified()

        def fake_generate(text):
            return {
                "ok": True,
                "reply": "image generated",
                "confidence": 0.99,
                "image_orchestrated": True,
                "visual_verified": True,
                "image_score": 0.95,
                "artifacts": ["test.png"],
            }

        core.image.run_generate = fake_generate
        out = core.chat("犬の絵を作成して", "v8762-image-routing")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("semantic-action-resolve", out["route"])
        self.assertIn("resource:image", out["route"])
        self.assertIn("action:create", out["route"])
        self.assertIn("image_generate", out["route"])
        self.assertNotIn("確定回答できません", out["reply"])


if __name__ == "__main__":
    unittest.main()
