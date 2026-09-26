from __future__ import annotations

from types import SimpleNamespace
import unittest

from fap_repository_executor import FileEdit
from fap_repository_repair_guard import GuardedRepairProvider


def attempt(errors=("focused_command_failed:test",)):
    verification = SimpleNamespace(errors=errors, commands=())
    return SimpleNamespace(verification=verification)


class GuardedRepairProviderTests(unittest.TestCase):
    def edit(self, content: str) -> FileEdit:
        return FileEdit(
            path="calc.py",
            operation="modify",
            before_sha256="a" * 64,
            content=content,
        )

    def test_rejects_unchanged_repair_candidate(self) -> None:
        current = (self.edit("x = 1\n"),)
        guard = GuardedRepairProvider(lambda edits, a: edits)
        self.assertIsNone(guard(current, attempt()))
        self.assertEqual(guard.last_decision.reason, "repair_candidate_unchanged")

    def test_allows_new_candidate_then_blocks_cycle(self) -> None:
        first = (self.edit("x = 1\n"),)
        second = (self.edit("x = 2\n"),)
        calls = [second, first]

        def provider(edits, a):
            return calls.pop(0)

        guard = GuardedRepairProvider(provider)
        self.assertEqual(guard(first, attempt()), second)
        self.assertTrue(guard.last_decision.allowed)
        self.assertIsNone(guard(second, attempt(("regression_command_failed:test",))))
        self.assertEqual(guard.last_decision.reason, "repair_candidate_cycle_detected")

    def test_repeated_candidate_failure_pair_stops_before_provider(self) -> None:
        current = (self.edit("x = 1\n"),)
        calls = []

        def provider(edits, a):
            calls.append(True)
            return (self.edit("x = 2\n"),)

        guard = GuardedRepairProvider(provider)
        self.assertIsNotNone(guard(current, attempt()))
        # Return to the same current candidate/failure pair after a caller-level reset.
        guard._seen_candidates = []
        self.assertIsNone(guard(current, attempt()))
        self.assertEqual(len(calls), 1)
        self.assertEqual(guard.last_decision.reason, "repeated_candidate_failure_pair")


if __name__ == "__main__":
    unittest.main()
