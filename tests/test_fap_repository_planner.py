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

    def test_reader_streams_late_symbol_window_under_small_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lines = [f"value_{i} = {i}\n" for i in range(320)]
            lines += [
                "\n",
                "def late_symbol(value: int) -> int:\n",
                "    return value + 7\n",
            ]
            (root / "large.py").write_text("".join(lines), encoding="utf-8")

            reader = RepositoryReader(
                root,
                max_files=1,
                max_total_bytes=420,
                max_file_bytes=420,
                dependency_hops=0,
            )
            context = reader.read("Inspect late_symbol in large.py")
            self.assertEqual(len(context.files), 1)
            target = context.files[0]
            self.assertEqual(target.path, "large.py")
            self.assertIn("def late_symbol", target.excerpt)
            self.assertLessEqual(target.excerpt_bytes, 420)

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

    def test_planner_keeps_dependency_neighbors_inspect_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryPlanner(root, max_files=5, max_source_bytes=5000)

            plan = planner.plan("Fix helper in pkg/util.py and run tests")
            target = next(f for f in plan.files if f.path == "pkg/util.py")
            self.assertEqual(target.operation, "modify")
            dependency_rows = [
                f for f in plan.files
                if f.path != "pkg/util.py"
                and "dependency_hop:" in f.reason
            ]
            self.assertTrue(dependency_rows)
            self.assertTrue(
                all(f.operation == "inspect" for f in dependency_rows)
            )

    def test_delete_requires_explicit_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryPlanner(root, max_files=5)

            ambiguous = planner.plan("Delete helper implementation")
            self.assertEqual(ambiguous.status, "insufficient_context")
            self.assertIn("ambiguous_delete_target", ambiguous.risk_flags)
            self.assertFalse(
                any(f.operation == "delete" for f in ambiguous.files)
            )

            explicit = planner.plan("Delete pkg/util.py")
            self.assertEqual(explicit.status, "ready")
            self.assertEqual(
                next(f for f in explicit.files if f.path == "pkg/util.py").operation,
                "delete",
            )
            self.assertTrue(
                all(
                    f.operation == "inspect"
                    for f in explicit.files
                    if f.path != "pkg/util.py"
                )
            )

    def test_missing_explicit_modify_target_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryPlanner(root, max_files=4)

            plan = planner.plan("Fix missing_module.py")
            self.assertEqual(plan.status, "insufficient_context")
            self.assertIn("explicit_target_missing", plan.risk_flags)
            self.assertFalse(
                any(f.operation == "modify" for f in plan.files)
            )

    def test_create_existing_target_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            planner = RepositoryPlanner(root, max_files=4)

            plan = planner.plan("Create new file pkg/util.py")
            self.assertEqual(plan.status, "insufficient_context")
            self.assertIn("create_target_exists", plan.risk_flags)
            self.assertFalse(
                any(f.operation == "create" for f in plan.files)
            )

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
