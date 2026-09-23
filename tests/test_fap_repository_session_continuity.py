from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_interaction_fabric import InteractionFabric, InteractionRequest
from fap_repository_executor import FileEdit
from fap_repository_interaction import RepositoryCodingInteraction
from fap_repository_session import RepositorySessionLedger
from fap_repository_verifier import VerificationCommand


class RepositorySessionContinuityTests(unittest.TestCase):
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

    def _commands(self) -> tuple[VerificationCommand, ...]:
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

    def test_ledger_is_content_free_and_digest_scoped(self) -> None:
        ledger = RepositorySessionLedger(max_sessions=2, max_paths=4)
        digest = "a" * 64
        plan_id = "b" * 64
        row = ledger.record(
            "chat-1",
            digest,
            plan_id,
            state="verified_candidate",
            paths=("calc.py", "tests/test_calc.py", "../escape.py"),
        )
        self.assertEqual(row.paths, ("calc.py", "tests/test_calc.py"))
        self.assertEqual(
            ledger.preferred_paths("chat-1", digest),
            ("calc.py", "tests/test_calc.py"),
        )
        self.assertEqual(ledger.preferred_paths("chat-1", "c" * 64), ())
        rendered = row.to_dict()
        self.assertNotIn("content", rendered)
        self.assertNotIn("diff", rendered)
        self.assertNotIn("source", rendered)

    def test_short_followup_reuses_previous_repository_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original = (root / "calc.py").read_text(encoding="utf-8")
            observed_plans: list[tuple[str, tuple[str, ...]]] = []

            def proposer(plan, context):
                paths = tuple(item.path for item in plan.files)
                observed_plans.append((plan.task.goal, paths))
                target = next(item for item in plan.files if item.path == "calc.py")
                return (
                    FileEdit(
                        path="calc.py",
                        operation="modify",
                        before_sha256=target.before_sha256,
                        content=original.replace(
                            "return value + 1",
                            "return int(value) + 1",
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
            meta = {"session_continuity": {"session_id": "coding-chat-1"}}

            first = fabric.dispatch(
                InteractionRequest(
                    text="Update calc.py implementation and run tests",
                    channel="chat",
                    metadata=meta,
                )
            )
            self.assertEqual(first.state, "handled")
            self.assertTrue((first.payload or {})["ok"])
            first_cont = (first.payload or {})["repository_session_continuity"]
            self.assertIn("calc.py", first_cont["remembered_paths"])

            second = fabric.dispatch(
                InteractionRequest(
                    text="Update it again and run tests",
                    history=(
                        {"role": "user", "text": "Update calc.py implementation and run tests"},
                        {"role": "assistant", "text": "verified candidate"},
                    ),
                    channel="chat",
                    metadata=meta,
                )
            )
            self.assertEqual(second.state, "handled")
            payload = second.payload or {}
            self.assertTrue(payload["ok"])
            continuity = payload["repository_session_continuity"]
            self.assertEqual(continuity["session_id"], "coding-chat-1")
            self.assertIn("calc.py", continuity["preferred_paths_used"])
            self.assertIn("calc.py", observed_plans[-1][1])
            self.assertEqual((root / "calc.py").read_text(encoding="utf-8"), original)
            self.assertEqual(self._git(root, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
