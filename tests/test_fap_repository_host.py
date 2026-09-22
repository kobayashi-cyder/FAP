from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_executor import FileEdit
from fap_repository_host import FAPRepositoryCodingHost, HOST_CONTRACT
from fap_repository_verifier import VerificationCommand


class RepositoryHostTests(unittest.TestCase):
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
        (root / "tests").mkdir()
        (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (root / "calc.py").write_text(
            "def add_one(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_calc.py").write_text(
            "import unittest\n"
            "from calc import add_one\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_add_one(self):\n"
            "        self.assertEqual(add_one(1), 2)\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def _commands(self):
        return (
            VerificationCommand(
                name="focused_calc",
                phase="focused",
                argv=(sys.executable, "-m", "unittest", "tests.test_calc", "-v"),
                timeout_sec=30,
            ),
            VerificationCommand(
                name="regression",
                phase="regression",
                argv=(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
                timeout_sec=30,
            ),
        )

    def test_verified_host_response_is_inert_summary_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")

            def proposer(plan, context):
                target = next(x for x in plan.files if x.path == "calc.py")
                return (
                    FileEdit(
                        path="calc.py",
                        operation="modify",
                        before_sha256=target.before_sha256,
                        content=original.replace("value + 1", "int(value) + 1"),
                    ),
                )

            host = FAPRepositoryCodingHost(
                root,
                proposer=proposer,
                commands=self._commands(),
                verified_progress=0.8,
            )
            response = host(
                "Fix calc.py implementation and run tests",
                "FCA observation should not be copied to source",
            )

            self.assertEqual(response.contract, HOST_CONTRACT)
            self.assertEqual(response.state, "verified_candidate")
            self.assertEqual(len(response.plan_id), 64)
            self.assertEqual(len(response.repository_digest), 64)
            self.assertEqual(response.progress, 0.8)
            self.assertEqual(response.attempts, 1)
            self.assertEqual(response.repairs_used, 0)
            self.assertIn("repository candidate verified", response.observation)

            rendered = repr(response.to_dict())
            self.assertNotIn("int(value) + 1", rendered)
            self.assertNotIn("FCA observation should not be copied", rendered)
            self.assertNotIn("diff", response.to_dict())
            self.assertNotIn("content", response.to_dict())

            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")
            self.assertEqual(
                self._git(root, "branch", "--list", "fap/candidate/*"),
                "",
            )

    def test_provider_error_message_is_not_exported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)

            def proposer(plan, context):
                raise RuntimeError("SECRET_TOKEN=/private/provider/path")

            host = FAPRepositoryCodingHost(
                root,
                proposer=proposer,
                commands=self._commands(),
            )
            response = host("Fix calc.py implementation and run tests")

            self.assertEqual(response.state, "rejected")
            self.assertEqual(
                response.reason,
                "proposal_provider_failed:RuntimeError",
            )
            rendered = repr(response.to_dict())
            self.assertNotIn("SECRET_TOKEN", rendered)
            self.assertNotIn("/private/provider/path", rendered)
            self.assertEqual(self._git(root, "status", "--porcelain"), "")

    def test_empty_or_oversized_goal_blocks_without_proposer_call(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            calls = []

            def proposer(plan, context):
                calls.append(True)
                return ()

            host = FAPRepositoryCodingHost(
                root,
                proposer=proposer,
                commands=self._commands(),
                max_goal_chars=256,
            )

            empty = host("")
            huge = host("x" * 257)

            self.assertEqual(empty.state, "blocked")
            self.assertEqual(empty.reason, "empty_goal")
            self.assertEqual(huge.state, "blocked")
            self.assertEqual(huge.reason, "goal_too_large")
            self.assertEqual(calls, [])

    def test_failed_verification_returns_rejected_without_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")

            def proposer(plan, context):
                target = next(x for x in plan.files if x.path == "calc.py")
                return (
                    FileEdit(
                        path="calc.py",
                        operation="modify",
                        before_sha256=target.before_sha256,
                        content=original.replace("value + 1", "value + 2"),
                    ),
                )

            host = FAPRepositoryCodingHost(
                root,
                proposer=proposer,
                commands=self._commands(),
            )
            response = host("Fix calc.py implementation and run tests")

            self.assertEqual(response.state, "rejected")
            self.assertEqual(response.progress, 0.0)
            self.assertTrue(response.plan_id)
            self.assertTrue(response.repository_digest)
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(
                self._git(root, "branch", "--list", "fap/candidate/*"),
                "",
            )


if __name__ == "__main__":
    unittest.main()
