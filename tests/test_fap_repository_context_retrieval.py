from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fap_repository_context_retrieval import RepositoryContextFusion


class RepositoryContextFusionTests(unittest.TestCase):
    def test_multi_query_fusion_promotes_shared_relevant_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "planner.py").write_text(
                "class RepositoryPlanner:\n    pass\n",
                encoding="utf-8",
            )
            (root / "reader.py").write_text(
                "from planner import RepositoryPlanner\n"
                "class RepositoryReader:\n    pass\n",
                encoding="utf-8",
            )
            (root / "unrelated.py").write_text("VALUE = 1\n", encoding="utf-8")
            ranked = RepositoryContextFusion(root).rank(
                (
                    "improve RepositoryReader context",
                    "planner dependency retrieval",
                )
            )
            self.assertTrue(ranked)
            paths = [row.path for row in ranked]
            self.assertIn("reader.py", paths)
            self.assertIn("planner.py", paths)
            self.assertNotIn("unrelated.py", paths)

    def test_explicit_path_gets_strong_boost(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("def target():\n    pass\n", encoding="utf-8")
            (root / "b.py").write_text("def target():\n    pass\n", encoding="utf-8")
            ranked = RepositoryContextFusion(root).rank(("update b.py target",))
            self.assertEqual(ranked[0].path, "b.py")
            self.assertIn("q0:exact_path", ranked[0].reasons)

    def test_empty_queries_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "non-empty query"):
                RepositoryContextFusion(root).rank(("", "  "))


if __name__ == "__main__":
    unittest.main()
