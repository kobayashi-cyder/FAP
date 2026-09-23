from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from fap_repository_diff_minimizer import RepositoryDiffMinimizer
from fap_repository_executor import FileEdit


class RepositoryDiffMinimizerTests(unittest.TestCase):
    def test_prefers_smaller_verified_candidate_surface(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "calc.py"
            source = "def add(a, b):\n    value = a + b\n    return value\n"
            path.write_text(source, encoding="utf-8")
            digest = sha256(source.encode("utf-8")).hexdigest()
            small = (
                FileEdit(
                    path="calc.py",
                    operation="modify",
                    before_sha256=digest,
                    content=source.replace("value = a + b", "value = int(a) + int(b)"),
                ),
            )
            large = (
                FileEdit(
                    path="calc.py",
                    operation="modify",
                    before_sha256=digest,
                    content=(
                        "def add(a, b):\n"
                        "    left = int(a)\n"
                        "    right = int(b)\n"
                        "    result = left + right\n"
                        "    return result\n"
                    ),
                ),
            )
            index, footprint = RepositoryDiffMinimizer(root).choose_smallest(
                (large, small)
            )
            self.assertEqual(index, 1)
            self.assertLess(
                footprint.total_changed_lines,
                RepositoryDiffMinimizer(root).measure(large).total_changed_lines,
            )

    def test_stale_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            edit = FileEdit(
                path="a.py",
                operation="modify",
                before_sha256="0" * 64,
                content="x = 2\n",
            )
            with self.assertRaisesRegex(ValueError, "STALE_EDIT"):
                RepositoryDiffMinimizer(root).measure((edit,))

    def test_create_and_delete_are_measured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old = "obsolete\n"
            (root / "old.md").write_text(old, encoding="utf-8")
            delete = FileEdit(
                path="old.md",
                operation="delete",
                before_sha256=sha256(old.encode("utf-8")).hexdigest(),
                content=None,
            )
            create = FileEdit(
                path="new.md",
                operation="create",
                before_sha256="",
                content="new\n",
            )
            result = RepositoryDiffMinimizer(root).measure((delete, create))
            self.assertEqual(len(result.files), 2)
            self.assertGreater(result.total_changed_lines, 0)


if __name__ == "__main__":
    unittest.main()
