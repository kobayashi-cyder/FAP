from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_executor import FileEdit
from fap_repository_multifile_transaction import RepositoryTransactionBuilder
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryTransactionBuilderTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True)

    def _fixture(self, root: Path):
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "x@example.invalid")
        self._git(root, "config", "user.name", "X")
        (root / "a.py").write_text("A = 1\n", encoding="utf-8")
        (root / "b.py").write_text("B = 1\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")
        return RepositoryStructuredPlanner(root).plan(
            "Update a.py and update b.py"
        )

    def test_transaction_is_order_independent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            by_path = {x.path: x for x in plan.files}
            a = FileEdit("a.py", "modify", by_path["a.py"].before_sha256, "A = 2\n")
            b = FileEdit("b.py", "modify", by_path["b.py"].before_sha256, "B = 2\n")
            builder = RepositoryTransactionBuilder()
            left = builder.build(plan, (a, b))
            right = builder.build(plan, (b, a))
            self.assertTrue(builder.equivalent(left, right))
            self.assertEqual(len(left.digest), 64)

    def test_missing_planned_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            row = next(x for x in plan.files if x.path == "a.py")
            a = FileEdit("a.py", "modify", row.before_sha256, "A = 2\n")
            with self.assertRaisesRegex(ValueError, "missing planned mutations"):
                RepositoryTransactionBuilder().build(plan, (a,))

    def test_unplanned_edit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            rogue = FileEdit("rogue.py", "create", "", "x=1\n")
            with self.assertRaisesRegex(ValueError, "unplanned transaction"):
                RepositoryTransactionBuilder().build(
                    plan,
                    (rogue,),
                    require_all_mutations=False,
                )


if __name__ == "__main__":
    unittest.main()
