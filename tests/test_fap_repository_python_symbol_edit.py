from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_python_symbol_edit import (
    PythonSymbolRenameError,
    PythonSymbolRenameSpec,
    RepositoryPythonTopLevelRenamer,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryPythonTopLevelRenamerTests(unittest.TestCase):
    def test_renames_definition_and_global_references_not_strings_or_comments(self) -> None:
        source = (
            "def old_name(value):\n"
            "    return value + 1\n\n"
            "def caller(value):\n"
            "    # old_name should remain in this comment\n"
            "    text = \"old_name\"\n"
            "    return old_name(value), text\n"
        )
        patched = RepositoryPythonTopLevelRenamer().rename(
            source,
            path="module.py",
            old_name="old_name",
            new_name="new_name",
        )
        self.assertIn("def new_name(value):", patched)
        self.assertIn("return new_name(value), text", patched)
        self.assertIn("# old_name should remain", patched)
        self.assertIn('text = "old_name"', patched)

    def test_ambiguous_local_binding_is_rejected(self) -> None:
        source = (
            "def target():\n"
            "    return 1\n\n"
            "def other():\n"
            "    target = 3\n"
            "    return target\n"
        )
        with self.assertRaisesRegex(PythonSymbolRenameError, "ambiguous_name_binding"):
            RepositoryPythonTopLevelRenamer().rename(
                source,
                path="module.py",
                old_name="target",
                new_name="renamed",
            )

    def test_build_edit_uses_plan_precondition(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "x@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "X"], check=True)
            (root / "module.py").write_text(
                "def old():\n    return 1\n\nVALUE = old()\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update module.py implementation"
            )
            edit = RepositoryPythonTopLevelRenamer().build_edit(
                root,
                plan,
                PythonSymbolRenameSpec("module.py", "old", "new"),
            )
            self.assertEqual(edit.operation, "modify")
            self.assertIn("def new():", edit.content or "")
            self.assertIn("VALUE = new()", edit.content or "")


if __name__ == "__main__":
    unittest.main()
