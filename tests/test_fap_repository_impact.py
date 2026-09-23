from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_impact import RepositoryImpactAnalyzer


class RepositoryImpactAnalyzerTests(unittest.TestCase):
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
        (root / "core.py").write_text(
            "def normalize(value: int) -> int:\n"
            "    return int(value)\n",
            encoding="utf-8",
        )
        (root / "service.py").write_text(
            "from core import normalize\n\n"
            "def compute(value: int) -> int:\n"
            "    return normalize(value) + 1\n",
            encoding="utf-8",
        )
        (root / "tests").mkdir()
        (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (root / "tests" / "test_service.py").write_text(
            "import unittest\n"
            "from service import compute\n\n"
            "class ServiceTests(unittest.TestCase):\n"
            "    def test_compute(self):\n"
            "        self.assertEqual(compute(2), 3)\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_reverse_dependency_walk_finds_indirect_test(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            report = RepositoryImpactAnalyzer(root, max_depth=2).analyze(("core.py",))

            self.assertEqual(report.seeds, ("core.py",))
            distances = {item.path: item.distance for item in report.impacted}
            self.assertEqual(distances["core.py"], 0)
            self.assertEqual(distances["service.py"], 1)
            self.assertEqual(distances["tests/test_service.py"], 2)
            self.assertEqual(report.test_paths, ("tests/test_service.py",))
            self.assertFalse(report.truncated)

    def test_depth_bound_prevents_unbounded_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            report = RepositoryImpactAnalyzer(root, max_depth=1).analyze(("core.py",))

            paths = {item.path for item in report.impacted}
            self.assertIn("service.py", paths)
            self.assertNotIn("tests/test_service.py", paths)
            self.assertEqual(report.test_paths, ())

    def test_unknown_seed_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            analyzer = RepositoryImpactAnalyzer(root)
            with self.assertRaisesRegex(ValueError, "unknown repository paths"):
                analyzer.analyze(("missing.py",))


if __name__ == "__main__":
    unittest.main()
