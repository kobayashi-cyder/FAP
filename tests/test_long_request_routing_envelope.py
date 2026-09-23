from __future__ import annotations

from pathlib import Path
import unittest

from fap_semantic_action_router import SemanticActionRouter
from fap_semantic_conversation import SemanticConversationRouter


ROOT = Path(__file__).resolve().parents[1]


class LongRequestRoutingEnvelopeTests(unittest.TestCase):
    def test_long_quoted_body_does_not_trigger_greeting_or_self_profile(self) -> None:
        router = SemanticConversationRouter(ROOT)
        text = (
            "次の試験問題を解き、指定されたキーだけで回答してください。"
            "\n\n"
            + ("本文では自分自身とは何かを説明する例や shinobu@example.jp が登場する。" * 80)
        )
        self.assertIsNone(router.match(text))

    def test_long_quoted_body_does_not_combine_resource_and_action_across_boundary(self) -> None:
        router = SemanticActionRouter(ROOT)
        text = (
            "次の問題をJSONで答えてください。"
            "\n\n"
            + ("教材ではプログラムを作成する手順を分析する。" * 100)
        )
        self.assertIsNone(router.match(text))

    def test_short_explicit_intents_still_route(self) -> None:
        conversation = SemanticConversationRouter(ROOT)
        action = SemanticActionRouter(ROOT)
        self.assertEqual((conversation.match("こんにちは") or {}).get("intent_id"), "greeting")
        self.assertEqual((conversation.match("FAPとは？") or {}).get("intent_id"), "self_profile")
        self.assertEqual((action.match("JSONを作成して") or {}).get("route"), "artifact_code_generate")


if __name__ == "__main__":
    unittest.main()
