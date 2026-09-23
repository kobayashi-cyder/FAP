from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_index import RepositoryIndexer
from fap_repository_performance import RepositoryIndexCache


class RepositoryIndexCacheTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True)

    def _fixture(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "x@example.invalid")
        self._git(root, "config", "user.name", "X")
        (root / "a.py").write_text("x = 1\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_clean_same_head_reuses_index(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            calls = []
            cache = RepositoryIndexCache(
                root,
                builder=lambda: calls.append(True) or RepositoryIndexer(root).build(),
            )
            first = cache.get()
            second = cache.get()
            self.assertIs(first, second)
            self.assertEqual(len(calls), 1)
            self.assertEqual(cache.stats.hits, 1)
            self.assertEqual(cache.stats.misses, 1)

    def test_dirty_tree_bypasses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            calls = []
            cache = RepositoryIndexCache(
                root,
                builder=lambda: calls.append(True) or RepositoryIndexer(root).build(),
            )
            cache.get()
            (root / "a.py").write_text("x = 2\n", encoding="utf-8")
            cache.get()
            cache.get()
            self.assertEqual(len(calls), 3)
            self.assertEqual(cache.stats.bypasses, 2)

    def test_new_commit_causes_cache_miss(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            calls = []
            cache = RepositoryIndexCache(
                root,
                builder=lambda: calls.append(True) or RepositoryIndexer(root).build(),
            )
            cache.get()
            (root / "a.py").write_text("x = 2\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "second")
            cache.get()
            self.assertEqual(len(calls), 2)
            self.assertEqual(cache.stats.misses, 2)


if __name__ == "__main__":
    unittest.main()
