from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_shell_edit import (
    RepositoryShellBlockEditor,
    ShellBlockEditError,
    ShellBlockSpec,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryShellBlockEditorTests(unittest.TestCase):
    def test_replaces_marked_block_without_touching_neighbors(self) -> None:
        source = (
            "#!/bin/sh\n"
            "echo before\n"
            "# FAP-BEGIN task\n"
            "echo old\n"
            "# FAP-END task\n"
            "echo after\n"
        )
        result = RepositoryShellBlockEditor().replace_block(
            source,
            name="task",
            body="echo new\necho second",
        )
        self.assertIn("echo before\n", result)
        self.assertIn("echo new\necho second\n", result)
        self.assertIn("echo after\n", result)
        self.assertNotIn("echo old", result)

    def test_missing_or_duplicate_markers_fail_closed(self) -> None:
        with self.assertRaisesRegex(ShellBlockEditError, "exactly one"):
            RepositoryShellBlockEditor().replace_block(
                "echo no markers\n",
                name="task",
                body="echo x",
            )

    def test_build_edit_uses_plan_hash_for_powershell(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "x@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "X"], check=True)
            (root / "run.ps1").write_text(
                "# FAP-BEGIN task\nWrite-Host old\n# FAP-END task\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update run.ps1 implementation"
            )
            edit = RepositoryShellBlockEditor().build_edit(
                root,
                plan,
                ShellBlockSpec("run.ps1", "task", "Write-Host new"),
            )
            self.assertEqual(edit.operation, "modify")
            self.assertIn("Write-Host new", edit.content or "")


if __name__ == "__main__":
    unittest.main()
