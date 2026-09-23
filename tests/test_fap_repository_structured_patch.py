from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_ast_patch import ASTPatchSpec
from fap_repository_structured_patch import (
    CreateTextSpec,
    DeleteFileSpec,
    ExactReplaceSpec,
    RepositoryStructuredProposalProvider,
    StructuredPatchError,
    structured_spec_from_mapping,
    structured_spec_to_dict,
)
from fap_repository_verifier import VerificationCommand


class RepositoryStructuredPatchTests(unittest.TestCase):
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
            "    return value + 2\n\n"
            "def times_two(value: int) -> int:\n"
            "    return value * 3\n",
            encoding="utf-8",
        )
        (root / "obsolete.md").write_text("old\n", encoding="utf-8")
        (root / "tests" / "test_calc.py").write_text(
            "import unittest\n"
            "from calc import add_one, times_two\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_add_one(self):\n"
            "        self.assertEqual(add_one(3), 4)\n\n"
            "    def test_times_two(self):\n"
            "        self.assertEqual(times_two(3), 6)\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def _commands(self) -> tuple[VerificationCommand, ...]:
        return (
            VerificationCommand(
                name="focused",
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

    def test_multiple_function_body_patches_compose_into_one_file_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")

            def specs(plan, context):
                return (
                    ASTPatchSpec(
                        path="calc.py",
                        target_symbol="add_one",
                        replacement_body="return value + 1",
                    ),
                    ASTPatchSpec(
                        path="calc.py",
                        target_symbol="times_two",
                        replacement_body="return value * 2",
                    ),
                )

            provider = RepositoryStructuredProposalProvider(root, specs)
            coordinator = RepositoryCodingCoordinator(root)
            result = coordinator.run(
                "Fix calc.py add_one and times_two implementation and run tests",
                provider,
                self._commands(),
            )

            self.assertEqual(result.state, "verified_candidate", result.errors)
            self.assertEqual(len(result.final_edits), 1)
            edit = result.final_edits[0]
            self.assertEqual(edit.path, "calc.py")
            self.assertIn("return value + 1", edit.content or "")
            self.assertIn("return value * 2", edit.content or "")
            self.assertEqual((root / "calc.py").read_text(encoding="utf-8"), original)
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_exact_replace_and_create_text_share_one_verified_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)

            def specs(plan, context):
                return (
                    ExactReplaceSpec(
                        path="calc.py",
                        old="return value + 2",
                        new="return value + 1",
                    ),
                    ExactReplaceSpec(
                        path="calc.py",
                        old="return value * 3",
                        new="return value * 2",
                    ),
                    CreateTextSpec(
                        path="notes.md",
                        content="# Coding notes\n\nGenerated on a non-main collaboration branch.\n",
                    ),
                )

            provider = RepositoryStructuredProposalProvider(root, specs)
            coordinator = RepositoryCodingCoordinator(root)
            result = coordinator.run(
                "Update calc.py and create new file notes.md then run tests",
                provider,
                self._commands(),
            )

            self.assertEqual(result.state, "verified_candidate", result.errors)
            self.assertEqual(
                {(item.path, item.operation) for item in result.final_edits},
                {("calc.py", "modify"), ("notes.md", "create")},
            )
            self.assertFalse((root / "notes.md").exists())
            self.assertIn(
                "return value + 2",
                (root / "calc.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_mapping_contract_round_trips_without_dynamic_code(self) -> None:
        rows = (
            {
                "op": "python_function_body",
                "path": "calc.py",
                "target_symbol": "add_one",
                "replacement_body": "return value + 1",
            },
            {
                "op": "replace_exact",
                "path": "README.md",
                "old": "old",
                "new": "new",
                "expected_count": 1,
            },
            {
                "op": "create_text",
                "path": "notes.md",
                "content": "hello\n",
            },
            {
                "op": "delete_file",
                "path": "obsolete.md",
            },
        )
        typed = tuple(structured_spec_from_mapping(row) for row in rows)
        rendered = tuple(structured_spec_to_dict(item) for item in typed)
        self.assertEqual(rendered, rows)
        self.assertIsInstance(typed[2], CreateTextSpec)
        self.assertIsInstance(typed[3], DeleteFileSpec)

    def test_exact_replace_requires_declared_match_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)
            plan = coordinator.planner.plan("Update calc.py implementation")
            provider = RepositoryStructuredProposalProvider(root, lambda p, c: ())

            with self.assertRaisesRegex(StructuredPatchError, "count mismatch"):
                provider.build_edits(
                    plan,
                    (
                        ExactReplaceSpec(
                            path="calc.py",
                            old="return",
                            new="yield",
                            expected_count=1,
                        ),
                    ),
                )

    def test_delete_requires_an_explicit_planned_delete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)
            plan = coordinator.planner.plan("Delete obsolete.md")
            provider = RepositoryStructuredProposalProvider(root, lambda p, c: ())
            edits = provider.build_edits(plan, (DeleteFileSpec(path="obsolete.md"),))
            self.assertEqual(len(edits), 1)
            self.assertEqual(edits[0].operation, "delete")
            self.assertIsNone(edits[0].content)


if __name__ == "__main__":
    unittest.main()
