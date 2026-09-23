from __future__ import annotations

import unittest

from fap_repository_chat_bridge import RepositoryChatBridge


class RepositoryChatBridgeTests(unittest.TestCase):
    def test_builds_content_minimized_request_with_file_hints(self) -> None:
        request = RepositoryChatBridge().build(
            "Update fap_repository_agent.py and run tests",
            history=(
                {"content": "Earlier we discussed tests/test_fap_repository_agent.py"},
                {"content": "Do not merge this directly to main"},
            ),
            branch="promote/chat-bridge-test",
            base_commit="a" * 40,
        )
        self.assertEqual(request.contract, "fap.repository.chat_bridge.v1")
        self.assertIn("fap_repository_agent.py", request.file_hints)
        self.assertIn("tests/test_fap_repository_agent.py", request.file_hints)
        self.assertEqual(len(request.history_digest), 64)
        rendered = repr(request.to_dict())
        self.assertNotIn("Earlier we discussed", rendered)
        self.assertNotIn("Do not merge", rendered)

    def test_main_branch_and_invalid_git_refs_are_rejected(self) -> None:
        for branch in ("main", "master", "a..b", "a@{b", "topic.lock", "a/.lock"):
            with self.subTest(branch=branch):
                with self.assertRaises(ValueError):
                    RepositoryChatBridge().build("Fix code", branch=branch)

    def test_claims_general_coding_intent(self) -> None:
        self.assertTrue(RepositoryChatBridge.claims("calc.pyを修正してテスト"))
        self.assertTrue(RepositoryChatBridge.claims("refactor the repository agent"))
        self.assertFalse(RepositoryChatBridge.claims("今日は天気どう？"))

    def test_bounds_are_fail_closed(self) -> None:
        bridge = RepositoryChatBridge()
        with self.assertRaisesRegex(ValueError, "max_file_hints"):
            bridge.build("Fix code", branch="topic", max_file_hints=-1)
        with self.assertRaisesRegex(ValueError, "max_history_rows"):
            bridge.build("Fix code", branch="topic", history=("a", "b"), max_history_rows=1)

    def test_zero_file_hint_limit_is_respected(self) -> None:
        request = RepositoryChatBridge().build(
            "Update fap_repository_agent.py",
            branch="topic",
            max_file_hints=0,
        )
        self.assertEqual(request.file_hints, ())

    def test_unpaired_surrogate_is_rejected(self) -> None:
        bridge = RepositoryChatBridge()
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            bridge.build("Fix \ud800 code", branch="topic")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            bridge.build("Fix code", branch="topic", history=("bad \ud800",))


if __name__ == "__main__":
    unittest.main()
