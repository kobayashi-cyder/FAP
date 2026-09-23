from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_js_ts import (
    JsFunctionBodySpec,
    RepositoryJsFunctionPatcher,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryJsFunctionPatcherTests(unittest.TestCase):
    def test_replaces_named_function_body_and_ignores_braces_in_strings(self) -> None:
        source = (
            "function target(value) {\n"
            "  const text = \"}\";\n"
            "  if (value) { return 1; }\n"
            "  return 0;\n"
            "}\n\n"
            "function other() { return 9; }\n"
        )
        patched = RepositoryJsFunctionPatcher().patch(
            source,
            path="app.js",
            function_name="target",
            replacement_body="const n = Number(value);\nreturn n + 1;",
        )
        self.assertIn("const n = Number(value);", patched)
        self.assertIn("function other() { return 9; }", patched)
        self.assertNotIn("const text", patched)

    def test_ambiguous_function_declaration_fails_closed(self) -> None:
        source = "function x() {}\nfunction x(a) { return a; }\n"
        with self.assertRaisesRegex(JsFunctionPatchError, "exactly one"):
            RepositoryJsFunctionPatcher().patch(
                source,
                path="app.js",
                function_name="x",
                replacement_body="return 1;",
            )

    def test_build_edit_uses_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "x@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "X"], check=True)
            (root / "app.ts").write_text(
                "function target(value: number) {\n  return value;\n}\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update app.ts implementation"
            )
            edit = RepositoryJsFunctionPatcher().build_edit(
                root,
                plan,
                JsFunctionBodySpec("app.ts", "target", "return value + 1;"),
            )
            self.assertEqual(edit.operation, "modify")
            self.assertIn("return value + 1;", edit.content or "")


if __name__ == "__main__":
    unittest.main()
