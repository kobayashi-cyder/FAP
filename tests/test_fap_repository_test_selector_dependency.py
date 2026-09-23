from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_test_selector import RepositoryVerificationSelector


class RepositoryVerificationDependencySelectionTests(unittest.TestCase):
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
            "def normalize(value):\n    return int(value)\n",
            encoding="utf-8",
        )
        (root / "service.py").write_text(
            "from core import normalize\n\ndef compute(value):\n    return normalize(value)+1\n",
            encoding="utf-8",
        )
        (root / "tests").mkdir()
        (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (root / "tests" / "test_service.py").write_text(
            "import unittest\nfrom service import compute\n\nclass T(unittest.TestCase):\n"
            "    def test_compute(self):\n        self.assertEqual(compute(2),3)\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_indirect_import_test_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryCodingCoordinator(root).planner.plan(
                "Update core.py implementation"
            )
            selection = RepositoryVerificationSelector(
                root,
                dependency_hops=2,
            ).select(plan)
            self.assertIn("tests/test_service.py", selection.focused_tests)
            self.assertIn("tests.test_service", selection.commands[0].argv)

    def test_zero_dependency_hops_falls_back_without_graph_walk(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryCodingCoordinator(root).planner.plan(
                "Update core.py implementation"
            )
            selection = RepositoryVerificationSelector(
                root,
                dependency_hops=0,
            ).select(plan)
            self.assertEqual(selection.focused_tests, ())
            self.assertIn(
                "focused_test_mapping_fell_back_to_discovery",
                selection.warnings,
            )


if __name__ == "__main__":
    unittest.main()
