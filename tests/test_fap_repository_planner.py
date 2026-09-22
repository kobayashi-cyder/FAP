from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from fap_repository_index import RepositoryIndexer
from fap_repository_planner import RepositoryPlanner
from fap_repository_reader import RepositoryReader


class RepositoryV8766Tests(unittest.TestCase):
    def _fixture(self, root: Path) -> None:
        (root / "pkg").mkdir()
        (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (root / "pkg" / "util.py").write_text(
            "def helper(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (root / "pkg" / "consumer.py").write_text(
            "from . import util\n\n"
            "def consume(value: int) -> int:\n"
            "    return util.helper(value)\n",
            encoding="utf-8",
        )
        (root / "app.py").write_text(
            "from pkg import util\n\n"
            "def run(value: int) -> int:\n"
            "    return util.helper(value)\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text("# Demo repository\n", encoding="utf-8")

    def test_index_resolves_imported_member_and_relative_import(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            idx = RepositoryIndexer(root).build()
            edges = {(e.source, e.target) for e in idx.dependencies}

            # Preserve the package edge from V87.65 while also exposing the
            # imported member module needed for repository-scale impact analysis.
            self.assertIn(("app.py", "pkg/__init__.py"), edges)
            self.assertIn(("app.py", "pkg/util.py"), edges)
            self.assertIn(("pkg/consumer.py", "pkg/util.py"), edges)

    def test_reader_selects_symbols_and_bounded_dependency_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            reader = RepositoryReader(
                root,
                max_files=4,
                max_total_bytes=2500,
                max_file_bytes=1200,
                dependency_hops=1,
            )
            context = reader.read("Fix helper in pkg/util.py")
            paths = {item.path for item in context.files}

            self.assertIn("pkg/util.py", paths)
            self.assertLessEqual(len(context.files), 4)
            self.assertLessEqual(sum(x.excerpt_bytes for x in context.files), 2500)
            self.assertTrue(all(not x.stale for x in context.files))
            self.assertTrue(any("helper" in x.excerpt for x in context.files if x.path == "pkg/util.py"))

    def test_reader_fails_closed_on_stale_indexed_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            idx = RepositoryIndexer(root).build()
            (root / "pkg" / "util.py").write_text(
                "def helper(value: int) -> int:\n"
                "    return value + 2\n",
                encoding="utf-8",
            )

            reader = RepositoryReader(root, index=idx, max_files=4)
            context = reader.read("Fix helper in pkg/util.py")
            target = next(x for x in context.files if x.path == "pkg/util.py")
            self.assertTrue(target.stale)
            self.assertEqual(target.excerpt, "")
            self.assertIn("stale_hash", target.reasons)

    def test_planner_is_deterministic_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            before = {
                p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*")
                if p.is_file()
            }

            planner = RepositoryPlanner(root, max_files=5, max_source_bytes=5000)
            first = planner.plan("Fix helper in pkg/util.py and run tests")
            second = planner.plan("Fix helper in pkg/util.py and run tests")

            after = {
                p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*")
                if p.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual(first.plan_id, second.plan_id)
            self.assertEqual(first.status, "ready")
            self.assertFalse(first.write_enabled)
            self.assertIn("sha_precondition", first.required_checks)
            self.assertIn("sandbox_only", first.required_checks)
            self.assertIn("regression_tests", first.required_checks)
            target = next(f for f in first.files if f.path == "pkg/util.py")
            self.assertEqual(target.operation, "modify")
            self.assertEqual(len(target.before_sha256), 64)

    def test_planner_can_describe_new_file_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryPlanner(root, max_files=4)

            plan = planner.plan("Create new file tools/new_tool.py")
            created = next(f for f in plan.files if f.path == "tools/new_tool.py")

            self.assertEqual(plan.status, "ready")
            self.assertEqual(created.operation, "create")
            self.assertEqual(created.before_sha256, "")
            self.assertIn("create_requested", plan.risk_flags)
            self.assertFalse((root / "tools" / "new_tool.py").exists())
            self.assertFalse(plan.write_enabled)


if __name__ == "__main__":
    unittest.main()
