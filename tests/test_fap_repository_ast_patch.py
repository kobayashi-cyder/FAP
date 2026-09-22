from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_ast_patch import (
    ASTLimitedProposalProvider,
    ASTLimitedRepairProvider,
    ASTPatchSpec,
    RepositoryASTFunctionPatcher,
)
from fap_repository_verifier import VerificationCommand


class RepositoryASTPatchSyncTests(unittest.TestCase):
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
            "def marker(fn):\n"
            "    return fn\n\n"
            "@marker\n"
            "def add_one(value: int) -> int:\n"
            "    \"\"\"Add one to a value.\"\"\"\n"
            "    converted = value\n"
            "    return converted + 1\n\n"
            "def untouched(value: int) -> int:\n"
            "    # byte-stable outside the target function\n"
            "    return value * 10\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_calc.py").write_text(
            "import unittest\n"
            "from calc import add_one, untouched\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_add_one_accepts_numeric_text(self):\n"
            "        self.assertEqual(add_one('1'), 2)\n\n"
            "    def test_untouched(self):\n"
            "        self.assertEqual(untouched(3), 30)\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def _commands(self) -> tuple[VerificationCommand, ...]:
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

    def test_patcher_preserves_signature_decorator_docstring_and_outside_bytes(self):
        source = (
            "def marker(fn):\n"
            "    return fn\n\n"
            "@marker\n"
            "def target(value: int = 1) -> int:\n"
            "    \"\"\"keep me\"\"\"\n"
            "    original = value\n"
            "    return original + 1\n\n"
            "TAIL = 'unchanged'\n"
        )
        patcher = RepositoryASTFunctionPatcher()
        result = patcher.patch(
            source,
            path="module.py",
            target_symbol="target",
            replacement_body="converted = int(value)\nreturn converted + 1",
        )

        self.assertTrue(result.ok, result.errors)
        self.assertIn("@marker\ndef target(value: int = 1) -> int:", result.content)
        self.assertIn('    \"\"\"keep me\"\"\"', result.content)
        self.assertIn("converted = int(value)", result.content)
        self.assertTrue(result.content.endswith("TAIL = 'unchanged'\n"))
        self.assertIn("signature_ast_equal", result.checks)
        self.assertIn("decorators_ast_equal", result.checks)
        self.assertIn("outside_region_byte_stable", result.checks)

    def test_patcher_rejects_forbidden_runtime_escape_primitives(self):
        patcher = RepositoryASTFunctionPatcher()
        source = "def target(value):\n    return value\n"
        for body in (
            "return eval(value)",
            "import subprocess\nreturn subprocess.run(value)",
            "return open(value).read()",
        ):
            result = patcher.patch(
                source,
                path="module.py",
                target_symbol="target",
                replacement_body=body,
            )
            self.assertFalse(result.ok, body)
            self.assertTrue(result.errors, body)

    def test_ast_limited_provider_runs_through_existing_repository_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")

            def specs(plan, context):
                return (
                    ASTPatchSpec(
                        path="calc.py",
                        target_symbol="add_one",
                        replacement_body="return int(value) + 1",
                    ),
                )

            provider = ASTLimitedProposalProvider(root, specs)
            coordinator = RepositoryCodingCoordinator(root)
            result = coordinator.run(
                "Fix calc.py add_one implementation and run tests",
                provider,
                self._commands(),
            )

            self.assertEqual(result.state, "verified_candidate")
            self.assertEqual(result.repair.state, "verified_candidate")
            self.assertEqual(len(result.final_edits), 1)
            self.assertIn("return int(value) + 1", result.final_edits[0].content or "")
            self.assertEqual((root / "calc.py").read_text(encoding="utf-8"), original)
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_ast_limited_repair_uses_existing_bounded_repair_loop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            coordinator = RepositoryCodingCoordinator(root, max_repairs=2)
            goal = "Fix calc.py add_one implementation and run tests"
            plan = coordinator.planner.plan(goal)

            def initial_specs(run_plan, context):
                self.assertEqual(run_plan.plan_id, plan.plan_id)
                return (
                    ASTPatchSpec(
                        path="calc.py",
                        target_symbol="add_one",
                        replacement_body="return int(value) + 2",
                    ),
                )

            proposal = ASTLimitedProposalProvider(root, initial_specs)

            def repair_specs(current, attempt):
                self.assertEqual(attempt.verification.state, "rejected")
                return (
                    ASTPatchSpec(
                        path="calc.py",
                        target_symbol="add_one",
                        replacement_body="return int(value) + 1",
                    ),
                )

            repair = ASTLimitedRepairProvider(proposal, plan, repair_specs)
            result = coordinator.run(
                goal,
                proposal,
                self._commands(),
                repairer=repair,
            )

            self.assertEqual(result.state, "verified_candidate")
            self.assertEqual(result.repair.repairs_used, 1)
            self.assertIn("return int(value) + 1", result.final_edits[0].content or "")
            self.assertEqual((root / "calc.py").read_text(encoding="utf-8"), original)
            self.assertEqual(self._git(root, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
