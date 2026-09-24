from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from fap_repository_chat_bridge import RepositoryChatBridge
from fap_repository_auto_orchestrator import (
    AUTO_CODING_VERSION,
    RepositoryAutoCodingOrchestrator,
)


class _Reader:
    def __init__(self, digest: str = "digest-a") -> None:
        self.digest = digest

    def read(self, goal, *, preferred_paths=()):
        return SimpleNamespace(repository_digest=self.digest)


class _Planner:
    def __init__(self) -> None:
        self.root = Path(".").resolve()
        self.reader = _Reader()
        self.calls = []
        self.plan = SimpleNamespace(
            plan_id="plan-1",
            task=SimpleNamespace(repository_digest="digest-a"),
        )

    def plan(self, goal, *, preferred_paths=()):
        self.calls.append((goal, preferred_paths))
        return self.plan


class _Coordinator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.planner = _Planner()
        self.planner.root = root


class _Chat:
    def __init__(self, root: Path) -> None:
        self.coordinator = _Coordinator(root)
        self.bridge = RepositoryChatBridge()
        self.run_calls = []
        self.result_plan = self.coordinator.planner.plan

    def prepare(self, current_text, *, history=(), branch, base_commit=""):
        return self.bridge.build(
            current_text,
            history=history,
            branch=branch,
            base_commit=base_commit,
        )

    def run(self, request, proposer, commands, *, repairer=None):
        self.run_calls.append(
            (request, proposer, tuple(commands), repairer)
        )
        return SimpleNamespace(
            state="verified_candidate",
            plan=self.coordinator.planner.current_plan,
            errors=(),
        )


class _Selector:
    def __init__(self) -> None:
        self.calls = []

    def select(self, plan):
        self.calls.append(plan)
        return SimpleNamespace(
            plan_id=plan.plan_id,
            commands=("auto-focused", "auto-regression"),
            warnings=(),
        )


class RepositoryAutoCodingOrchestratorTests(unittest.TestCase):
    def _make(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name).resolve()
        chat = _Chat(root)
        selector = _Selector()
        orchestrator = RepositoryAutoCodingOrchestrator(
            root,
            chat=chat,
            selector=selector,
        )
        return td, orchestrator, chat, selector

    def test_prepare_automatically_selects_verification(self) -> None:
        td, orchestrator, chat, selector = self._make()
        self.addCleanup(td.cleanup)

        prepared = orchestrator.prepare(
            "Update fap_repository_agent.py and test it",
            history=("Earlier: tests/test_fap_repository_agent.py",),
            branch="horiz/auto-test",
            base_commit="a" * 40,
        )

        self.assertEqual(prepared.version, AUTO_CODING_VERSION)
        self.assertEqual(prepared.plan.plan_id, "plan-1")
        self.assertEqual(
            prepared.verification.commands,
            ("auto-focused", "auto-regression"),
        )
        self.assertEqual(len(selector.calls), 1)
        self.assertIn(
            "fap_repository_agent.py",
            prepared.request.file_hints,
        )
        self.assertIn(
            "tests/test_fap_repository_agent.py",
            prepared.request.file_hints,
        )

    def test_stale_context_blocks_before_execution(self) -> None:
        td, orchestrator, chat, _ = self._make()
        self.addCleanup(td.cleanup)

        prepared = orchestrator.prepare(
            "Update a.py",
            branch="horiz/auto-test",
        )
        chat.coordinator.planner.reader.digest = "digest-b"

        outcome = orchestrator.run(prepared, object())

        self.assertEqual(outcome.state, "blocked")
        self.assertIsNone(outcome.result)
        self.assertEqual(chat.run_calls, [])
        self.assertIn(
            "repository_context_changed_after_prepare",
            outcome.errors[0],
        )

    def test_run_forwards_auto_selected_commands_and_repairer(self) -> None:
        td, orchestrator, chat, _ = self._make()
        self.addCleanup(td.cleanup)

        prepared = orchestrator.prepare(
            "Fix a.py",
            branch="horiz/auto-test",
        )
        proposer = object()
        repairer = object()

        outcome = orchestrator.run(
            prepared,
            proposer,
            repairer=repairer,
        )

        self.assertEqual(outcome.state, "verified_candidate")
        self.assertEqual(len(chat.run_calls), 1)
        _, forwarded, commands, forwarded_repairer = chat.run_calls[0]
        self.assertIs(forwarded, proposer)
        self.assertEqual(
            commands,
            ("auto-focused", "auto-regression"),
        )
        self.assertIs(forwarded_repairer, repairer)

    def test_plan_change_during_run_never_claims_verified(self) -> None:
        td, orchestrator, chat, _ = self._make()
        self.addCleanup(td.cleanup)

        prepared = orchestrator.prepare(
            "Fix a.py",
            branch="horiz/auto-test",
        )
        chat.coordinator.planner.current_plan = SimpleNamespace(
            plan_id="plan-2",
            task=SimpleNamespace(repository_digest="digest-a"),
        )

        outcome = orchestrator.run(prepared, object())

        self.assertEqual(outcome.state, "rejected")
        self.assertIn(
            "auto_orchestrator:plan_changed_during_run",
            outcome.errors,
        )

    def test_tampered_verification_plan_id_is_rejected(self) -> None:
        td, orchestrator, _, _ = self._make()
        self.addCleanup(td.cleanup)

        prepared = orchestrator.prepare(
            "Fix a.py",
            branch="horiz/auto-test",
        )
        tampered = replace(
            prepared,
            verification=SimpleNamespace(
                plan_id="other-plan",
                commands=(),
                warnings=(),
            ),
        )

        with self.assertRaisesRegex(ValueError, "plan_id mismatch"):
            orchestrator.run(tampered, object())

    def test_main_branch_is_rejected_by_chat_contract(self) -> None:
        td, orchestrator, _, _ = self._make()
        self.addCleanup(td.cleanup)

        with self.assertRaisesRegex(ValueError, "non-main branch"):
            orchestrator.prepare(
                "Fix a.py",
                branch="main",
            )


if __name__ == "__main__":
    unittest.main()
