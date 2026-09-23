from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_structured_agent import RepositoryStructuredCodingAgent
from fap_repository_structured_patch import CreateTextSpec, ExactReplaceSpec


class RepositoryStructuredCodingAgentTests(unittest.TestCase):
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
            "    return int(value) + 1\n",
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

    def test_integrated_agent_selects_indirect_test_and_verifies_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "core.py").read_text(encoding="utf-8")
            agent = RepositoryStructuredCodingAgent(root)

            def provider(plan, context):
                return (
                    ExactReplaceSpec(
                        path="core.py",
                        old="return int(value) + 1",
                        new="return int(value)",
                    ),
                )

            run = agent.run("Update core.py implementation", provider)

            self.assertEqual(run.state, "verified_candidate", run.errors)
            self.assertIn("tests/test_service.py", run.verification.focused_tests)
            self.assertIn("tests/test_service.py", run.verification.dependency_tests)
            self.assertEqual(run.coding.state, "verified_candidate")
            self.assertEqual((root / "core.py").read_text(encoding="utf-8"), original)
            self.assertEqual(self._git(root, "status", "--porcelain"), "")
            self.assertEqual(self._git(root, "branch", "--list", "fap/candidate/*"), "")

    def test_integrated_agent_handles_mixed_modify_and_create_without_source_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            agent = RepositoryStructuredCodingAgent(root)

            def provider(plan, context):
                return (
                    ExactReplaceSpec(
                        path="core.py",
                        old="return int(value) + 1",
                        new="return int(value)",
                    ),
                    CreateTextSpec(
                        path="notes.md",
                        content="# Candidate notes\n\nVerified outside main.\n",
                    ),
                )

            run = agent.run(
                "Update core.py and create new file notes.md",
                provider,
            )

            self.assertEqual(run.state, "verified_candidate", run.errors)
            ops = {(item.path, item.operation) for item in run.coding.final_edits}
            self.assertEqual(
                ops,
                {("core.py", "modify"), ("notes.md", "create")},
            )
            self.assertFalse((root / "notes.md").exists())
            self.assertIn(
                "return int(value) + 1",
                (root / "core.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_missing_tests_do_not_become_verified_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "fap-tests@example.invalid")
            self._git(root, "config", "user.name", "FAP Tests")
            (root / "core.py").write_text(
                "def normalize(value):\n"
                "    return value + 1\n",
                encoding="utf-8",
            )
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "fixture")
            agent = RepositoryStructuredCodingAgent(root)

            run = agent.run(
                "Update core.py implementation",
                lambda plan, context: (
                    ExactReplaceSpec(
                        path="core.py",
                        old="return value + 1",
                        new="return value",
                    ),
                ),
            )

            self.assertEqual(run.state, "rejected")
            self.assertIn(
                "focused_tests_required_but_tests_directory_is_empty",
                run.verification.warnings,
            )


if __name__ == "__main__":
    unittest.main()
