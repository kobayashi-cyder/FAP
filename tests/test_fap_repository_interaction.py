from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_interaction_fabric import InteractionFabric, InteractionRequest
from fap_repository_executor import FileEdit
from fap_repository_interaction import RepositoryCodingInteraction
from fap_repository_verifier import VerificationCommand


class RepositoryInteractionTests(unittest.TestCase):
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
                name="focused",
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

    def test_chat_selected_repository_endpoint_verifies_without_source_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")

            def proposer(plan, context):
                target = next(item for item in plan.files if item.path == "calc.py")
                return (
                    FileEdit(
                        path="calc.py",
                        operation="modify",
                        before_sha256=target.before_sha256,
                        content=original.replace(
                            "value + 1",
                            "int(value) + 1",
                        ),
                    ),
                )

            adapter = RepositoryCodingInteraction(
                root,
                proposer=proposer,
                commands=self._commands(),
                scorer=lambda request: 1.0,
            )
            fabric = InteractionFabric()
            fabric.register(adapter.endpoint())

            result = fabric.dispatch(
                InteractionRequest(
                    text="Fix calc.py implementation and run tests",
                    history=({"content": "previous repository discussion"},),
                    channel="chat",
                    pressure_hint=0.8,
                )
            )

            self.assertEqual(result.state, "handled")
            self.assertEqual(result.endpoint_id, "repository_coding")
            payload = result.payload or {}
            self.assertTrue(payload["ok"])
            self.assertEqual(
                payload["repository_coding"]["state"],
                "verified_candidate",
            )
            budget = payload["adaptive_repository_budget"]
            self.assertGreaterEqual(budget["max_files"], 4)
            self.assertLessEqual(budget["max_files"], 32)
            self.assertLessEqual(budget["max_source_bytes"], 1_000_000)
            self.assertLessEqual(budget["max_repairs"], 4)
            self.assertGreaterEqual(budget["scale"], 1.0)

            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")
            self.assertEqual(
                self._git(root, "branch", "--list", "fap/candidate/*"),
                "",
            )

    def test_zero_score_does_not_invoke_repository_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            calls = []

            def proposer(plan, context):
                calls.append(True)
                return ()

            adapter = RepositoryCodingInteraction(
                root,
                proposer=proposer,
                commands=self._commands(),
                scorer=lambda request: 0.0,
            )
            fabric = InteractionFabric()
            fabric.register(adapter.endpoint())
            result = fabric.dispatch(
                InteractionRequest("ordinary chat", channel="chat")
            )
            self.assertEqual(result.state, "unhandled")
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
