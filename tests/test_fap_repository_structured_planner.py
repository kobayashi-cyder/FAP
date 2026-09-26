from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryStructuredPlannerTests(unittest.TestCase):
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
        (root / "calc.py").write_text(
            "def add_one(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (root / "obsolete.md").write_text("# old\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_mixed_modify_and_create_are_planned_per_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryStructuredPlanner(root)
            plan = planner.plan("Update calc.py and create new file notes.md")

            self.assertEqual(plan.status, "ready", plan.risk_flags)
            ops = {item.path: item.operation for item in plan.files}
            self.assertEqual(ops.get("calc.py"), "modify")
            self.assertEqual(ops.get("notes.md"), "create")
            self.assertNotIn("create_target_exists", plan.risk_flags)
            self.assertIn("create_requested", plan.risk_flags)

    def test_mixed_delete_and_modify_are_planned_per_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryStructuredPlanner(root)
            plan = planner.plan("Delete obsolete.md and update calc.py")

            self.assertEqual(plan.status, "ready", plan.risk_flags)
            ops = {item.path: item.operation for item in plan.files}
            self.assertEqual(ops.get("obsolete.md"), "delete")
            self.assertEqual(ops.get("calc.py"), "modify")
            self.assertIn("delete_requested", plan.risk_flags)

    def test_japanese_suffix_operations_are_resolved_per_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryStructuredPlanner(root)
            plan = planner.plan("calc.pyを修正して obsolete.mdを削除")

            self.assertEqual(plan.status, "ready", plan.risk_flags)
            ops = {item.path: item.operation for item in plan.files}
            self.assertEqual(ops.get("calc.py"), "modify")
            self.assertEqual(ops.get("obsolete.md"), "delete")

    def test_create_existing_target_stays_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryStructuredPlanner(root)
            plan = planner.plan("Create new file calc.py")

            self.assertEqual(plan.status, "insufficient_context")
            self.assertIn("create_target_exists", plan.risk_flags)
            target = next(item for item in plan.files if item.path == "calc.py")
            self.assertEqual(target.operation, "inspect")

    def test_missing_modify_target_stays_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryStructuredPlanner(root)
            plan = planner.plan("Update missing.py")

            self.assertEqual(plan.status, "insufficient_context")
            self.assertIn("explicit_target_missing", plan.risk_flags)
            self.assertFalse(plan.write_enabled)


if __name__ == "__main__":
    unittest.main()
