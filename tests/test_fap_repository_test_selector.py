from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_structured_patch import (
    ExactReplaceSpec,
    RepositoryStructuredProposalProvider,
)
from fap_repository_test_selector import RepositoryVerificationSelector


class RepositoryVerificationSelectorTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        return proc.stdout

    def _fixture(self, root: Path, *, with_tests: bool = True) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "fap-tests@example.invalid")
        self._git(root, "config", "user.name", "FAP Tests")
        (root / "calc.py").write_text(
            "def add_one(value: int) -> int:\n"
            "    return value + 2\n",
            encoding="utf-8",
        )
        if with_tests:
            (root / "tests").mkdir()
            (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
            (root / "tests" / "test_calc.py").write_text(
                "import unittest\n"
                "from calc import add_one\n\n"
                "class CalcTests(unittest.TestCase):\n"
                "    def test_add_one(self):\n"
                "        self.assertEqual(add_one(2), 3)\n",
                encoding="utf-8",
            )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_selects_related_focused_test_and_regression_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)
            plan = coordinator.planner.plan("Update calc.py implementation")
            selection = RepositoryVerificationSelector(root).select(plan)

            self.assertEqual(selection.plan_id, plan.plan_id)
            self.assertEqual(selection.focused_tests, ("tests/test_calc.py",))
            self.assertEqual(selection.regression_strategy, "unittest_discover")
            self.assertEqual(
                tuple(command.phase for command in selection.commands),
                ("focused", "regression"),
            )
            self.assertIn("tests.test_calc", selection.commands[0].argv)
            self.assertFalse(selection.warnings)

    def test_selected_commands_drive_verified_candidate_without_manual_test_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)
            goal = "Update calc.py implementation"
            plan = coordinator.planner.plan(goal)
            selection = RepositoryVerificationSelector(root).select(plan)

            def specs(run_plan, context):
                self.assertEqual(run_plan.plan_id, plan.plan_id)
                return (
                    ExactReplaceSpec(
                        path="calc.py",
                        old="return value + 2",
                        new="return value + 1",
                    ),
                )

            provider = RepositoryStructuredProposalProvider(root, specs)
            result = coordinator.run(goal, provider, selection.commands)

            self.assertEqual(result.state, "verified_candidate", result.errors)
            self.assertEqual(result.repair.repairs_used, 0)
            self.assertIn("return value + 1", result.final_edits[0].content or "")
            self.assertIn(
                "return value + 2",
                (root / "calc.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_missing_tests_remains_fail_closed_signal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root, with_tests=False)
            coordinator = RepositoryCodingCoordinator(root)
            plan = coordinator.planner.plan("Update calc.py implementation")
            selection = RepositoryVerificationSelector(root).select(plan)

            self.assertEqual(selection.commands, ())
            self.assertIn(
                "focused_tests_required_but_tests_directory_is_empty",
                selection.warnings,
            )
            self.assertIn(
                "regression_tests_required_but_tests_directory_is_empty",
                selection.warnings,
            )
            self.assertEqual(selection.regression_strategy, "unavailable")


if __name__ == "__main__":
    unittest.main()
