from __future__ import annotations

from dataclasses import replace
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
        return RepositoryStructuredPlanner(root).plan("Update a.py and update b.py")

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

    def test_protocol_version_is_part_of_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            by_path = {x.path: x for x in plan.files}
            edits = (
                FileEdit("a.py", "modify", by_path["a.py"].before_sha256, "A = 2\n"),
                FileEdit("b.py", "modify", by_path["b.py"].before_sha256, "B = 2\n"),
            )
            builder = RepositoryTransactionBuilder()
            transaction = builder.build(plan, edits)
            unsupported = replace(transaction, version="fap.repository.transaction.v999")
            self.assertFalse(builder.equivalent(transaction, unsupported))

    def test_missing_planned_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            row = next(x for x in plan.files if x.path == "a.py")
            with self.assertRaisesRegex(ValueError, "missing planned mutations"):
                RepositoryTransactionBuilder().build(plan, (FileEdit("a.py", "modify", row.before_sha256, "A = 2\n"),))

    def test_unplanned_edit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            with self.assertRaisesRegex(ValueError, "unplanned transaction"):
                RepositoryTransactionBuilder().build(plan, (FileEdit("rogue.py", "create", "", "x=1\n"),), require_all_mutations=False)

    def test_operation_and_before_hash_must_match_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._fixture(root)
            row = next(x for x in plan.files if x.path == "a.py")
            builder = RepositoryTransactionBuilder()
            with self.assertRaisesRegex(ValueError, "operation mismatch"):
                builder.build(plan, (FileEdit("a.py", "delete", row.before_sha256, None),), require_all_mutations=False)
            with self.assertRaisesRegex(ValueError, "before hash mismatch"):
                builder.build(plan, (FileEdit("a.py", "modify", "0" * 64, "A = 2\n"),), require_all_mutations=False)


if __name__ == "__main__":
    unittest.main()
