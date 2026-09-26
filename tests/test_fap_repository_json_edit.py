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

    def test_valid_empty_and_dot_named_keys_can_be_set_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root, '{"":0,".":1,"..":2}\n')
            edit = RepositoryJsonEditor().build_edit(root, self._plan(root), (
                JsonSetSpec("config.json", ("",), 10),
                JsonSetSpec("config.json", (".",), 11),
                JsonDeleteSpec("config.json", ("..",)),
            ))
            obj = json.loads(edit.content or "")
            self.assertEqual(obj[""], 10)
            self.assertEqual(obj["."], 11)
            self.assertNotIn("..", obj)

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

    def test_explicit_null_intermediate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root, '{"feature":null}\n')
            with self.assertRaisesRegex(RuntimeError, "intermediate key is not an object"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("feature", "enabled"), True),))

    def test_unpaired_surrogate_result_is_rejected_before_file_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root)
            with self.assertRaisesRegex(RuntimeError, "not strictly serializable"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("x",), "\ud800"),))

    def test_unpaired_surrogate_from_source_is_rejected_after_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self._fixture(root, '{"x":"\\ud800","feature":{}}\n')
            with self.assertRaisesRegex(RuntimeError, "not strictly serializable"):
                RepositoryJsonEditor().build_edit(root, self._plan(root), (JsonSetSpec("config.json", ("feature", "enabled"), True),))


if __name__ == "__main__":
    unittest.main()
