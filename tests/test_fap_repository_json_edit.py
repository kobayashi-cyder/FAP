from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_json_edit import (
    JsonDeleteSpec,
    JsonSetSpec,
    RepositoryJsonEditor,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryJsonEditorTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True)

    def _fixture(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "x@example.invalid")
        self._git(root, "config", "user.name", "X")
        (root / "config.json").write_text(
            '{"feature":{"enabled":false,"old":1}}\n',
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_semantic_set_and_delete_emit_one_file_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update config.json implementation"
            )
            edit = RepositoryJsonEditor().build_edit(
                root,
                plan,
                (
                    JsonSetSpec("config.json", ("feature", "enabled"), True),
                    JsonSetSpec("config.json", ("feature", "limit"), 3),
                    JsonDeleteSpec("config.json", ("feature", "old")),
                ),
            )
            obj = json.loads(edit.content or "")
            self.assertTrue(obj["feature"]["enabled"])
            self.assertEqual(obj["feature"]["limit"], 3)
            self.assertNotIn("old", obj["feature"])
            self.assertEqual(edit.operation, "modify")

    def test_non_object_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "x@example.invalid")
            self._git(root, "config", "user.name", "X")
            (root / "config.json").write_text("[]\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "fixture")
            plan = RepositoryStructuredPlanner(root).plan(
                "Update config.json implementation"
            )
            with self.assertRaisesRegex(RuntimeError, "root must be an object"):
                RepositoryJsonEditor().build_edit(
                    root,
                    plan,
                    (JsonSetSpec("config.json", ("x",), 1),),
                )


if __name__ == "__main__":
    unittest.main()
