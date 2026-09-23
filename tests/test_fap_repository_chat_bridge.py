from __future__ import annotations

import unittest

from fap_repository_chat_bridge import RepositoryChatBridge


class RepositoryChatBridgeTests(unittest.TestCase):
    def test_builds_content_minimized_request_with_file_hints(self) -> None:
        bridge = RepositoryChatBridge()
        request = bridge.build(
            "Update fap_repository_agent.py and run tests",
            history=(
                {"content": "Earlier we discussed tests/test_fap_repository_agent.py"},
                {"content": "Do not merge this directly to main"},
            ),
            branch="horiz/coding-chat-bridge",
            base_commit="a" * 40,
        )
        self.assertEqual(request.contract, "fap.repository.chat_bridge.v1")
        self.assertEqual(request.branch, "horiz/coding-chat-bridge")
        self.assertIn("fap_repository_agent.py", request.file_hints)
        self.assertIn("tests/test_fap_repository_agent.py", request.file_hints)
        self.assertEqual(len(request.history_digest), 64)
        rendered = repr(request.to_dict())
        self.assertNotIn("Earlier we discussed", rendered)
        self.assertNotIn("Do not merge", rendered)

    def test_main_branch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-main"):
            RepositoryChatBridge().build(
                "Fix code",
                branch="main",
            )

    def test_claims_general_coding_intent(self) -> None:
        self.assertTrue(RepositoryChatBridge.claims("calc.pyを修正してテスト"))
        self.assertTrue(RepositoryChatBridge.claims("refactor the repository agent"))
        self.assertFalse(RepositoryChatBridge.claims("今日は天気どう？"))


if __name__ == "__main__":
    unittest.main()
