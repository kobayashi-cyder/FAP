from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_python_insert import (
    PythonFunctionInsertSpec,
    RepositoryPythonFunctionInserter,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryPythonFunctionInserterTests(unittest.TestCase):
    def test_appends_function_and_preserves_existing_source_prefix(self) -> None:
        source = "VALUE = 1\n\ndef existing(x):\n    return x + VALUE\n"
        result = RepositoryPythonFunctionInserter().insert(
            source,
            path="module.py",
            function_source="def added(value: int) -> int:\n    return value * 2",
        )
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.content.startswith(source))
        self.assertIn("def added(value: int) -> int:", result.content)

    def test_duplicate_symbol_and_forbidden_runtime_escape_are_rejected(self) -> None:
        source = "def existing(x):\n    return x\n"
        duplicate = RepositoryPythonFunctionInserter().insert(
            source,
            path="module.py",
            function_source="def existing(x):\n    return x + 1",
        )
        self.assertFalse(duplicate.ok)
        self.assertIn("symbol_already_exists", duplicate.errors)

        forbidden = RepositoryPythonFunctionInserter().insert(
            source,
            path="module.py",
            function_source="def added(x):\n    return eval(x)",
        )
        self.assertFalse(forbidden.ok)
        self.assertIn("forbidden_call:eval", forbidden.errors)

    def test_from_plan_emits_sha_guarded_file_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "x@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "X"], check=True)
            (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            plan = RepositoryStructuredPlanner(root).plan("Update module.py implementation")
            edit = RepositoryPythonFunctionInserter().from_plan(
                root,
                plan,
                PythonFunctionInsertSpec(
                    path="module.py",
                    function_source="def added():\n    return VALUE + 1",
                ),
            )
            self.assertEqual(edit.operation, "modify")
            self.assertTrue(edit.before_sha256)
            self.assertIn("def added():", edit.content or "")


if __name__ == "__main__":
    unittest.main()
