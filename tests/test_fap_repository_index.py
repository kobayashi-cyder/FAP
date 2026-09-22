from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fap_repository_index import RepositoryIndexer, build_repository_context, render_repository_map


class RepositoryIndexerTests(unittest.TestCase):
    def test_builds_symbol_and_dependency_index_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "pkg" / "util.py").write_text(
                "def helper(x: int) -> int:\n"
                "    return x + 1\n",
                encoding="utf-8",
            )
            (root / "app.py").write_text(
                "from pkg import util\n\n"
                "class Runner:\n"
                "    def run(self, value: int = 1) -> int:\n"
                "        return util.helper(value)\n",
                encoding="utf-8",
            )
            # This file would fail if executed, but indexing must never execute it.
            (root / "danger.py").write_text(
                "raise RuntimeError('must not execute')\n"
                "def still_indexed():\n"
                "    return 1\n",
                encoding="utf-8",
            )

            idx = RepositoryIndexer(root).build()
            by_path = {f.path: f for f in idx.files}
            self.assertEqual(by_path["app.py"].parse_status, "parsed")
            names = {(s.name, s.kind) for s in by_path["app.py"].symbols}
            self.assertIn(("Runner", "class"), names)
            self.assertIn(("run", "method"), names)
            self.assertIn(("still_indexed", "function"), {(s.name, s.kind) for s in by_path["danger.py"].symbols})
            self.assertTrue(any(e.source == "app.py" and e.target == "pkg/__init__.py" for e in idx.dependencies))

    def test_size_limit_skips_large_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "large.py").write_text("x = 1\n" * 100, encoding="utf-8")
            idx = RepositoryIndexer(root, max_file_bytes=20).build()
            rec = next(f for f in idx.files if f.path == "large.py")
            self.assertEqual(rec.parse_status, "skipped:size_limit")
            self.assertEqual(rec.symbols, ())

    def test_render_is_deterministic_and_contains_signatures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text(
                "async def fetch(x: str, *, retries: int = 2) -> str:\n"
                "    return x\n",
                encoding="utf-8",
            )
            idx1 = RepositoryIndexer(root).build()
            idx2 = RepositoryIndexer(root).build()
            text1 = render_repository_map(idx1)
            text2 = render_repository_map(idx2)
            self.assertEqual(text1, text2)
            self.assertIn("async def fetch(", text1)
            self.assertIn("retries: int=2", text1)

    def test_adapter_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "x.py").write_text("def x():\n    return 1\n", encoding="utf-8")
            out = build_repository_context(root)
            self.assertIn("index", out)
            self.assertIn("map", out)
            self.assertIn("x.py", out["map"])


if __name__ == "__main__":
    unittest.main()
