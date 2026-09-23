from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_markdown_edit import (
    MarkdownEditError,
    MarkdownSectionSpec,
    RepositoryMarkdownEditor,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryMarkdownEditorTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True)

    def test_replaces_only_target_section(self) -> None:
        source = (
            "# Title\n\n"
            "intro\n\n"
            "## Coding\n\n"
            "old body\n\n"
            "### Detail\n\n"
            "old detail\n\n"
            "## Other\n\n"
            "keep me\n"
        )
        result = RepositoryMarkdownEditor().replace_section(
            source,
            heading="Coding",
            body="new body\n\n### Detail\n\nnew detail",
        )
        self.assertIn("new body", result)
        self.assertNotIn("old body", result)
        self.assertIn("## Other\n\nkeep me\n", result)
        self.assertTrue(result.startswith("# Title\n\nintro"))

    def test_duplicate_heading_fails_closed(self) -> None:
        source = "## A\n\none\n\n## A\n\ntwo\n"
        with self.assertRaisesRegex(MarkdownEditError, "exactly one"):
            RepositoryMarkdownEditor().replace_section(
                source,
                heading="A",
                body="new",
            )

    def test_build_edit_uses_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "x@example.invalid")
            self._git(root, "config", "user.name", "X")
            (root / "README.md").write_text(
                "# Title\n\n## Coding\n\nold\n",
                encoding="utf-8",
            )
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "fixture")
            plan = RepositoryStructuredPlanner(root).plan(
                "Update README.md documentation"
            )
            edit = RepositoryMarkdownEditor().build_edit(
                root,
                plan,
                MarkdownSectionSpec("README.md", "Coding", "new"),
            )
            self.assertEqual(edit.operation, "modify")
            self.assertTrue(edit.before_sha256)
            self.assertIn("new", edit.content or "")


if __name__ == "__main__":
    unittest.main()
