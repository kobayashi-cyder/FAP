from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
V69 = ROOT.parents[1] / "v69" / "interaction"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(V69))

from fap_managed_chat import ManagedChatSession


class ManagedChatTests(unittest.TestCase):
    def test_status_clear_and_undo_controls_do_not_call_responder(self):
        calls = []
        def responder(text, context, mode):
            calls.append(text)
            return "ok"

        chat = ManagedChatSession()
        self.assertIn("mode=rich", chat.submit(":status", responder))
        self.assertEqual(calls, [])

        chat.submit("one", responder)
        self.assertEqual(len(chat.turns), 2)
        self.assertEqual(chat.submit(":undo", responder), "chat_undo=1")
        self.assertEqual(len(chat.turns), 0)
        self.assertEqual(chat.submit(":undo", responder), "chat_undo=0")

        chat.submit("two", responder)
        self.assertEqual(chat.submit(":clear", responder), "chat_cleared")
        self.assertEqual(len(chat.turns), 0)

    def test_mode_command_and_legacy_mode_command(self):
        chat = ManagedChatSession()
        responder = lambda text, context, mode: mode
        self.assertEqual(chat.submit(":mode brief", responder), "mode=brief")
        self.assertEqual(chat.mode, "brief")
        self.assertEqual(chat.submit(":verbose", responder), "mode=verbose")
        self.assertEqual(chat.mode, "verbose")

    def test_exchange_limit_preserves_pairs(self):
        chat = ManagedChatSession(max_exchanges=2)
        responder = lambda text, context, mode: "r:" + text
        for value in ("one", "two", "three"):
            chat.submit(value, responder)
        self.assertEqual(len(chat.turns), 4)
        self.assertEqual([t.role for t in chat.turns], ["user", "assistant", "user", "assistant"])
        self.assertEqual(chat.turns[0].text, "two")

    def test_context_budget_drops_old_pairs(self):
        chat = ManagedChatSession(
            max_exchanges=10,
            max_context_chars=100,
            max_input_chars=40,
            max_stored_assistant_chars=40,
        )
        responder = lambda text, context, mode: "R" * 35
        for value in ("A" * 20, "B" * 20, "C" * 20):
            chat.submit(value, responder)
        self.assertLessEqual(chat.status().context_chars, 100)
        self.assertEqual(len(chat.turns) % 2, 0)

    def test_large_response_is_returned_full_but_storage_is_clipped(self):
        chat = ManagedChatSession(
            max_context_chars=120,
            max_input_chars=40,
            max_stored_assistant_chars=30,
        )
        response = chat.submit("hello", lambda *_: "Z" * 200)
        self.assertEqual(len(response), 200)
        self.assertLessEqual(len(chat.turns[-1].text), 30)
        self.assertIn("…", chat.turns[-1].text)
        self.assertLessEqual(chat.status().context_chars, 120)

    def test_single_pair_is_forced_within_context_budget(self):
        chat = ManagedChatSession(
            max_context_chars=64,
            max_input_chars=40,
            max_stored_assistant_chars=40,
        )
        chat.submit("U" * 40, lambda *_: "A" * 100)
        self.assertLessEqual(chat.status().context_chars, 64)
        self.assertEqual(len(chat.turns), 2)

    def test_oversized_input_and_empty_input_rejected(self):
        chat = ManagedChatSession(max_context_chars=100, max_input_chars=10)
        with self.assertRaises(ValueError):
            chat.submit("x" * 11, lambda *_: "ok")
        with self.assertRaises(ValueError):
            chat.submit("   ", lambda *_: "ok")

    def test_status_is_deterministic_and_contains_no_message_content(self):
        chat = ManagedChatSession()
        chat.submit("secret-ish text", lambda *_: "answer")
        status = chat.status()
        rendered = repr(status)
        self.assertNotIn("secret-ish", rendered)
        self.assertNotIn("answer", rendered)


if __name__ == "__main__":
    unittest.main()
