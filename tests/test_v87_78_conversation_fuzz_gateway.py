from __future__ import annotations

import json
from pathlib import Path
import unittest

import fap_v87_78_conversation_fuzz_gateway as g
from fap_conversation_fuzz import generate_conversation_corpus
from fap_semantic_action_router import SemanticActionRouter


ROOT = Path(__file__).resolve().parents[1]


class V8778GatewayFuzzTests(unittest.TestCase):
    def setUp(self):
        self.core = g.FAPV8778Unified()
        self.sid = "v8778-conversation-fuzz"
        self.path = g.base.MEMORY.path(self.sid)
        if self.path.exists():
            self.path.unlink()
        self.core.clear_route_continuity(self.sid)
        self.action_router = SemanticActionRouter(ROOT)

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()
        self.core.clear_route_continuity(self.sid)

    def _strict_json(self, value) -> None:
        json.dumps(value, ensure_ascii=False, allow_nan=False)

    def test_randomized_latest_gateway_chat_does_not_raise(self):
        exercised = 0
        for case in generate_conversation_corpus(ROOT, seed=8778001, count=4096):
            if exercised >= 96:
                break
            if not case.text.strip() or len(case.text) > 320:
                continue

            # Keep this lane conversation-only. Action routes (image/repository/code)
            # have their own execution tests and can intentionally perform expensive work.
            if self.action_router.match(case.text) is not None:
                continue

            result = self.core.chat(case.text, self.sid)
            self.assertIsInstance(result, dict)
            self.assertIn("reply", result)
            self.assertIsInstance(result.get("reply"), str)
            self.assertIn("verdict", result)
            self._strict_json(result)
            exercised += 1

        self.assertEqual(exercised, 96)

        persisted = g.base.MEMORY.load(self.sid)
        self.assertGreaterEqual(len(persisted), 2)
        snapshot = self.core.session_routes.snapshot(self.sid).to_dict()
        self._strict_json(snapshot)

    def test_randomized_multi_turn_context_remains_bounded(self):
        texts = []
        for case in generate_conversation_corpus(ROOT, seed=8778002, count=1024):
            if case.text.strip() and len(case.text) <= 180:
                texts.append(case.text)
            if len(texts) >= 48:
                break

        for text in texts:
            result = self.core.chat(text, self.sid)
            context = result.get("adaptive_session_context") or {}
            self.assertLessEqual(
                int(context.get("selected_turns", 0)),
                self.core.session_context.max_turns,
            )
            self.assertLessEqual(
                int(context.get("selected_chars", 0)),
                self.core.session_context.hard_context_chars,
            )

        self.assertEqual(len(texts), 48)


if __name__ == "__main__":
    unittest.main()
