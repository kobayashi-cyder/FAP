from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import fap_semantic_conversation as semantic_module
from fap_semantic_conversation import RuntimeSelfProfile, SemanticConversationRouter
from fap_v87_59_semantic_conversation_gateway import FAPV8759Unified


class SemanticConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.router = SemanticConversationRouter(cls.root)
        cls.profile = RuntimeSelfProfile(cls.router)

    def test_multiple_self_intro_paraphrases_share_one_semantic_intent(self):
        prompts = [
            "FAPを紹介して下さい",
            "自己紹介してください。",
            "あなたについて教えて",
            "FAPとは何ですか？",
        ]
        ids = []
        for prompt in prompts:
            match = self.router.match(prompt)
            self.assertIsNotNone(match, prompt)
            ids.append(match["intent_id"])
            self.assertEqual(match["response_mode"], "runtime_self_profile")
        self.assertTrue(all(i == "self_profile" for i in ids))

    def test_capability_question_is_data_driven(self):
        match = self.router.match("FAPは何ができる？")
        self.assertIsNotNone(match)
        self.assertEqual(match["intent_id"], "capability_overview")
        self.assertEqual(match["response_mode"], "runtime_self_profile")

    def test_greeting_is_data_driven_and_device_neutral(self):
        out = self.profile.run(
            "こんにちは",
            version="87.59-unified-chat",
            capabilities=(),
            status={"version": "87.59-unified-chat"},
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["semantic_intent"], "greeting")
        self.assertIn("87.59-unified-chat", out["reply"])
        self.assertNotIn("Pixel", out["reply"])

    def test_profile_is_rendered_from_runtime_capabilities(self):
        out = self.profile.run(
            "FAPを紹介して下さい",
            version="87.59-unified-chat",
            capabilities=(
                "generic-symbolic-derivation",
                "generic-semantic-rule-chaining",
                "semantic-long-term-memory",
                "image-orchestrator:v87.56",
            ),
            status={"version": "87.59-unified-chat"},
        )
        self.assertIsNotNone(out)
        self.assertIn("87.59-unified-chat", out["reply"])
        self.assertIn("generic-symbolic-derivation", out["reply"])
        self.assertIn("generic-semantic-rule-chaining", out["reply"])
        self.assertNotIn("V78で蒸留した", out["reply"])

    def test_router_source_does_not_contain_screenshot_specific_utterance(self):
        source = inspect.getsource(semantic_module)
        self.assertNotIn("FAPを紹介して下さい", source)
        self.assertNotIn("自己紹介してください", source)

    def test_latest_chat_fixes_screenshot_failure_end_to_end(self):
        core = FAPV8759Unified()
        out = core.chat("FAPを紹介して下さい", "v8759-self-profile")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("semantic-conversation-intent", out["route"])
        self.assertIn("dynamic-self-profile", out["route"])
        self.assertIn("87.59-unified-chat", out["reply"])
        self.assertNotIn("確定回答できません", out["reply"])

    def test_latest_chat_keeps_self_intro_paraphrase_consistent(self):
        core = FAPV8759Unified()
        a = core.chat("FAPを紹介して下さい", "v8759-paraphrase-a")
        b = core.chat("自己紹介してください。", "v8759-paraphrase-b")
        self.assertEqual(a["verdict"], "OK")
        self.assertEqual(b["verdict"], "OK")
        self.assertIn("87.59-unified-chat", a["reply"])
        self.assertIn("87.59-unified-chat", b["reply"])
        self.assertNotIn("V78で蒸留した", b["reply"])


if __name__ == "__main__":
    unittest.main()
