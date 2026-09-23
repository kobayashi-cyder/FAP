from __future__ import annotations

from dataclasses import replace
import unittest

from fap_repository_chat_bridge import RepositoryChatBridge
from fap_repository_chat_coding import RepositoryChatCodingCoordinator


class _FakeCoordinator:
    def __init__(self) -> None:
        self.calls = []

    def run(self, goal, proposer, commands, *, repairer=None, preferred_paths=()):
        self.calls.append((goal, proposer, tuple(commands), repairer, preferred_paths))
        return "result"


class RepositoryChatCodingCoordinatorTests(unittest.TestCase):
    def test_prepared_request_is_forwarded_to_real_coding_contract(self) -> None:
        fake = _FakeCoordinator()
        adapter = RepositoryChatCodingCoordinator(".", coordinator=fake)
        request = adapter.prepare(
            "Update fap_repository_agent.py",
            history=("Earlier: tests/test_fap_repository_agent.py",),
            branch="promote/chat-bridge-test",
            base_commit="a" * 40,
        )
        proposer = object()
        result = adapter.run(request, proposer, ())
        self.assertEqual(result, "result")
        goal, forwarded, commands, repairer, paths = fake.calls[0]
        self.assertEqual(goal, request.goal)
        self.assertIs(forwarded, proposer)
        self.assertEqual(commands, ())
        self.assertIsNone(repairer)
        self.assertEqual(paths, request.file_hints)

    def test_unknown_contract_is_rejected_before_coding(self) -> None:
        fake = _FakeCoordinator()
        adapter = RepositoryChatCodingCoordinator(".", coordinator=fake)
        request = RepositoryChatBridge().build("Fix code", branch="topic")
        request = replace(request, contract="unknown")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            adapter.run(request, object(), ())
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
