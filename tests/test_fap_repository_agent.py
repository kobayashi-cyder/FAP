from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_executor import FileEdit
from fap_repository_promotion import PromotionApproval
from fap_repository_verifier import VerificationCommand


class RepositoryV8770Tests(unittest.TestCase):
    def _git(self, root: Path, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if check and proc.returncode != 0:
            raise AssertionError(proc.stdout)
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
            "        self.assertEqual(add_one(1), 2)\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

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

    def _edit_for(self, plan, content: str) -> FileEdit:
        target = next(x for x in plan.files if x.path == "calc.py")
        return FileEdit(
            path="calc.py",
            operation="modify",
            before_sha256=target.before_sha256,
            content=content,
        )

    def test_coordinator_runs_to_verified_candidate_without_auto_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root)

            def proposer(plan, context):
                self.assertEqual(plan.task.repository_digest, context.repository_digest)
                self.assertTrue(any(x.path == "calc.py" for x in context.files))
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "int(value) + 1"),
                    ),
                )

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
            )

            self.assertEqual(result.state, "verified_candidate")
            self.assertIsNotNone(result.repair)
            self.assertEqual(result.repair.state, "verified_candidate")
            self.assertEqual(len(result.final_edits), 1)
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")
            self.assertEqual(self._git(root, "branch", "--list", "fap/candidate/*"), "")

    def test_coordinator_tracks_final_repaired_edits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root, max_repairs=2)

            def proposer(plan, context):
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "value + 2"),
                    ),
                )

            def repairer(current, attempt):
                self.assertEqual(attempt.verification.state, "rejected")
                plan = coordinator.planner.plan(
                    "Fix calc.py implementation and run tests"
                )
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "int(value) + 1"),
                    ),
                )

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
                repairer=repairer,
            )

            self.assertEqual(result.state, "verified_candidate")
            self.assertEqual(result.repair.repairs_used, 1)
            self.assertIn("int(value) + 1", result.final_edits[0].content or "")
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )

    def test_repair_cycle_guard_stops_unchanged_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root, max_repairs=4)
            calls = []

            def proposer(plan, context):
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "value + 2"),
                    ),
                )

            def repairer(current, attempt):
                calls.append(attempt.round_index)
                return current

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
                repairer=repairer,
            )

            self.assertEqual(result.state, "rejected")
            self.assertIsNotNone(result.repair)
            self.assertEqual(len(result.repair.attempts), 1)
            self.assertEqual(calls, [0])
            self.assertIn("value + 2", result.final_edits[0].content or "")
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )

    def test_proposal_provider_exception_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)

            def proposer(plan, context):
                raise RuntimeError("provider unavailable")

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
            )

            self.assertEqual(result.state, "rejected")
            self.assertTrue(
                any(x.startswith("proposal_provider_failed:") for x in result.errors)
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_invalid_proposal_is_rejected_by_security_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)

            def proposer(plan, context):
                return (
                    FileEdit(
                        path="../escape.py",
                        operation="modify",
                        before_sha256="0" * 64,
                        content="bad = True\n",
                    ),
                )

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
            )

            self.assertEqual(result.state, "rejected")
            self.assertIsNone(result.repair)
            self.assertIn(
                "security_policy:unsafe_repository_path",
                result.errors,
            )
            self.assertFalse((root.parent / "escape.py").exists())
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_path_qualified_fake_python_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root)

            def proposer(plan, context):
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "int(value) + 1"),
                    ),
                )

            commands = (
                VerificationCommand(
                    name="focused_calc",
                    phase="focused",
                    argv=(str(root / "python"), "-V"),
                    timeout_sec=30,
                ),
                self._commands()[1],
            )
            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                commands,
            )

            self.assertEqual(result.state, "rejected")
            self.assertIsNone(result.repair)
            self.assertIn(
                "security_policy:executable_path_not_allowed",
                result.errors,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_repair_candidate_is_rechecked_by_security_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root, max_repairs=2)

            def proposer(plan, context):
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "value + 2"),
                    ),
                )

            def repairer(current, attempt):
                return (
                    FileEdit(
                        path="../escape.py",
                        operation="modify",
                        before_sha256="0" * 64,
                        content="bad = True\n",
                    ),
                )

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
                repairer=repairer,
            )

            self.assertEqual(result.state, "rejected")
            self.assertIn(
                "security_policy:unsafe_repository_path",
                result.errors,
            )
            self.assertFalse((root.parent / "escape.py").exists())
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_explicit_promote_verified_rechecks_and_creates_candidate_branch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root)

            def proposer(plan, context):
                return (
                    self._edit_for(
                        plan,
                        original.replace("value + 1", "int(value) + 1"),
                    ),
                )

            result = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
            )
            base = self._git(root, "rev-parse", "HEAD").strip()
            promoted = coordinator.promote_verified(
                result,
                self._commands(),
                PromotionApproval(
                    plan_id=result.plan.plan_id,
                    expected_base_commit=base,
                    allow_candidate_branch=True,
                    reason="V87.70 explicit integration promotion test",
                ),
            )

            self.assertEqual(promoted.state, "candidate_branch_created")
            self.assertIsNotNone(promoted.branch)
            self.assertEqual(self._git(root, "rev-parse", "HEAD").strip(), base)
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )


if __name__ == "__main__":
    unittest.main()
