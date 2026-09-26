from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_executor import FileEdit, RepositoryPatchExecutor
from fap_repository_planner import RepositoryPlanner
from fap_repository_verifier import (
    BoundedRepairLoop,
    RepositoryVerifier,
    VerificationCommand,
)


class RepositoryV8768Tests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        return proc.stdout

    def _fixture(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "fap-tests@example.invalid")
        self._git(root, "config", "user.name", "FAP Tests")
        (root / "tests").mkdir()
        (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (root / "calc.py").write_text(
            "def add_one(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_calc.py").write_text(
            "import unittest\n"
            "from calc import add_one\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_add_one(self):\n"
            "        self.assertEqual(add_one(1), 2)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def _plan_and_target(self, root: Path):
        plan = RepositoryPlanner(root, max_files=5).plan(
            "Fix calc.py implementation and run tests"
        )
        target = next(x for x in plan.files if x.path == "calc.py")
        return plan, target

    def _commands(self):
        return (
            VerificationCommand(
                name="focused_calc",
                phase="focused",
                argv=(sys.executable, "-m", "unittest", "tests.test_calc", "-v"),
                timeout_sec=30,
            ),
            VerificationCommand(
                name="regression",
                phase="regression",
                argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
                timeout_sec=30,
            ),
        )

    def test_verified_candidate_passes_static_focused_and_regression(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            plan, target = self._plan_and_target(root)
            edit = FileEdit(
                path="calc.py",
                operation="modify",
                before_sha256=target.before_sha256,
                content=original.replace("value + 1", "int(value) + 1"),
            )
            executor = RepositoryPatchExecutor(root)
            verifier = RepositoryVerifier()

            with executor.open(plan) as session:
                execution = session.apply((edit,))
                report = verifier.verify(session, execution, self._commands())

            self.assertEqual(report.state, "verified_candidate")
            self.assertTrue(report.static_passed)
            self.assertTrue(all(x.passed for x in report.commands))
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_static_compile_rejects_invalid_python_before_tests(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan, target = self._plan_and_target(root)
            edit = FileEdit(
                path="calc.py",
                operation="modify",
                before_sha256=target.before_sha256,
                content="def add_one(value: int) -> int:\n    return (\n",
            )
            executor = RepositoryPatchExecutor(root)
            verifier = RepositoryVerifier()

            with executor.open(plan) as session:
                execution = session.apply((edit,))
                report = verifier.verify(session, execution, self._commands())

            self.assertEqual(report.state, "rejected")
            self.assertIn("static_compile_failed", report.errors)
            self.assertEqual(len(report.commands), 1)
            self.assertEqual(report.commands[0].phase, "static")

    def test_missing_required_test_commands_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            plan, target = self._plan_and_target(root)
            edit = FileEdit(
                path="calc.py",
                operation="modify",
                before_sha256=target.before_sha256,
                content=original.replace("value + 1", "int(value) + 1"),
            )
            executor = RepositoryPatchExecutor(root)
            verifier = RepositoryVerifier()

            with executor.open(plan) as session:
                execution = session.apply((edit,))
                report = verifier.verify(session, execution, ())

            self.assertEqual(report.state, "rejected")
            self.assertIn("missing_required_focused_tests", report.errors)

    def test_bounded_repair_uses_fresh_worktree_and_stops_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            plan, target = self._plan_and_target(root)
            bad = FileEdit(
                path="calc.py",
                operation="modify",
                before_sha256=target.before_sha256,
                content=original.replace("value + 1", "value + 2"),
            )
            good = FileEdit(
                path="calc.py",
                operation="modify",
                before_sha256=target.before_sha256,
                content=original.replace("value + 1", "int(value) + 1"),
            )
            repair_calls = []

            def repairer(current, attempt):
                repair_calls.append((current, attempt))
                self.assertEqual(attempt.verification.state, "rejected")
                return (good,)

            loop = BoundedRepairLoop(
                RepositoryPatchExecutor(root),
                RepositoryVerifier(),
                max_repairs=2,
            )
            report = loop.run(
                plan,
                (bad,),
                self._commands(),
                repairer=repairer,
            )

            self.assertEqual(report.state, "verified_candidate")
            self.assertEqual(report.repairs_used, 1)
            self.assertEqual(len(report.attempts), 2)
            self.assertEqual(len(repair_calls), 1)
            self.assertEqual(
                report.attempts[0].verification.state,
                "rejected",
            )
            self.assertEqual(
                report.attempts[1].verification.state,
                "verified_candidate",
            )
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_command_policy_rejects_shell_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            plan, target = self._plan_and_target(root)
            edit = FileEdit(
                path="calc.py",
                operation="modify",
                before_sha256=target.before_sha256,
                content=original.replace("value + 1", "int(value) + 1"),
            )
            executor = RepositoryPatchExecutor(root)
            verifier = RepositoryVerifier()

            with executor.open(plan) as session:
                execution = session.apply((edit,))
                report = verifier.verify(
                    session,
                    execution,
                    (
                        VerificationCommand(
                            name="shell",
                            phase="focused",
                            argv=("sh", "-c", "exit 0"),
                        ),
                    ),
                )

            self.assertEqual(report.state, "rejected")
            self.assertTrue(any(x.startswith("command_policy:") for x in report.errors))


if __name__ == "__main__":
    unittest.main()
