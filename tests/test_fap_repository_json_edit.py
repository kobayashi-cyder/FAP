from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_json_edit import JsonDeleteSpec, JsonSetSpec, RepositoryJsonEditor
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryJsonEditorTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True)

    def _fixture(self, root: Path, content: str = '{"feature":{"enabled":false,"old":1}}\n') -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "x@example.invalid")
        self._git(root, "config", "user.name", "X")
        (root / "config.json").write_text(content, encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def _plan(self, root: Path):
        return RepositoryStructuredPlanner(root).plan("Update config.json implementation")

    def test_semantic_set_and_delete_emit_one_file_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root)
            edit = RepositoryJsonEditor().build_edit(root, self._plan(root), (
                JsonSetSpec("config.json", ("feature", "enabled"), True),
                JsonSetSpec("config.json", ("feature", "limit"), 3),
                JsonDeleteSpec("config.json", ("feature", "old")),
            ))
            obj = json.loads(edit.content or "")
            self.assertTrue(obj["feature"]["enabled"])
            self.assertEqual(obj["feature"]["limit"], 3)
            self.assertNotIn("old", obj["feature"])
            self.assertEqual(edit.operation, "modify")

    def test_non_object_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root, "[]\n")
            with self.assertRaisesRegex(RuntimeError, "root must be an object"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("x",), 1),))

    def test_duplicate_source_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root, '{"x":1,"x":2}\n')
            with self.assertRaisesRegex(RuntimeError, "invalid or ambiguous"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("x",), 3),))

    def test_non_finite_source_number_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root, '{"x":NaN}\n')
            with self.assertRaisesRegex(RuntimeError, "invalid or ambiguous"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("x",), 3),))

    def test_non_finite_result_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root)
            with self.assertRaisesRegex(RuntimeError, "not strictly serializable"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("x",), float("nan")),))

    def test_stale_plan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root)
            plan = self._plan(root)
            (root / "config.json").write_text('{"changed":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "STALE_PLAN"):
                RepositoryJsonEditor().build_edit(root, plan, (JsonSetSpec("config.json", ("x",), 1),))

    def test_indent_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root)
            with self.assertRaisesRegex(RuntimeError, "indent"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("x",), 1),), indent=1000)


if __name__ == "__main__":
    unittest.main()
