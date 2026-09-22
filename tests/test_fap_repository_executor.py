from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_executor import FileEdit, RepositoryPatchExecutor
from fap_repository_planner import RepositoryPlanner


class RepositoryV8767Tests(unittest.TestCase):
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
        (root / "pkg").mkdir()
        (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (root / "pkg" / "util.py").write_text(
            "def helper(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (root / "app.py").write_text(
            "from pkg import util\n\n"
            "def run(value: int) -> int:\n"
            "    return util.helper(value)\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text("# executor fixture\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_modify_is_applied_only_inside_temporary_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "pkg" / "util.py").read_text(encoding="utf-8")
            planner = RepositoryPlanner(root, max_files=5)
            plan = planner.plan("Fix pkg/util.py helper implementation")
            target = next(x for x in plan.files if x.path == "pkg/util.py")
            replacement = original.replace("value + 1", "value + 2")

            report = RepositoryPatchExecutor(root).execute(
                plan,
                [
                    FileEdit(
                        path=target.path,
                        operation="modify",
                        before_sha256=target.before_sha256,
                        content=replacement,
                    )
                ],
            )

            self.assertEqual(report.state, "applied_in_sandbox")
            self.assertFalse(report.errors)
            self.assertIn("value + 2", report.diff)
            self.assertEqual(
                (root / "pkg" / "util.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_create_is_visible_in_diff_but_not_created_in_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryPlanner(root, max_files=4)
            plan = planner.plan("Create new file tools/new_tool.py")
            target = next(x for x in plan.files if x.path == "tools/new_tool.py")

            report = RepositoryPatchExecutor(root).execute(
                plan,
                [
                    FileEdit(
                        path=target.path,
                        operation="create",
                        before_sha256="",
                        content="def ping() -> str:\n    return 'pong'\n",
                    )
                ],
            )

            self.assertEqual(report.state, "applied_in_sandbox")
            self.assertIn("new_tool.py", report.diff)
            self.assertIn("return 'pong'", report.diff)
            self.assertFalse((root / "tools" / "new_tool.py").exists())
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_executor_rejects_stale_repository_digest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryPlanner(root).plan("Fix pkg/util.py helper")
            (root / "README.md").write_text("# changed after planning\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "STALE_PLAN"):
                RepositoryPatchExecutor(root).open(plan)

    def test_executor_rejects_unplanned_or_escaping_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryPlanner(root).plan("Fix pkg/util.py helper")
            report = RepositoryPatchExecutor(root).execute(
                plan,
                [
                    FileEdit(
                        path="../escape.py",
                        operation="modify",
                        before_sha256="0" * 64,
                        content="bad = True\n",
                    )
                ],
            )
            self.assertEqual(report.state, "rejected")
            self.assertTrue(report.errors)
            self.assertFalse((root.parent / "escape.py").exists())

    def test_open_session_exposes_sandbox_then_cleans_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "pkg" / "util.py").read_text(encoding="utf-8")
            plan = RepositoryPlanner(root).plan("Fix pkg/util.py helper")
            target = next(x for x in plan.files if x.path == "pkg/util.py")
            executor = RepositoryPatchExecutor(root)

            with executor.open(plan) as session:
                sandbox_path = session.path
                report = session.apply(
                    [
                        FileEdit(
                            path=target.path,
                            operation="modify",
                            before_sha256=target.before_sha256,
                            content=original.replace("value + 1", "value + 7"),
                        )
                    ]
                )
                self.assertEqual(report.state, "applied_in_sandbox")
                self.assertTrue(sandbox_path.exists())
                self.assertIn(
                    "value + 7",
                    (sandbox_path / "pkg" / "util.py").read_text(encoding="utf-8"),
                )
                self.assertEqual(
                    (root / "pkg" / "util.py").read_text(encoding="utf-8"),
                    original,
                )

            self.assertFalse(sandbox_path.exists())


if __name__ == "__main__":
    unittest.main()
