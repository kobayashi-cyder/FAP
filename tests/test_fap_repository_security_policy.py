from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_executor import FileEdit
from fap_repository_security_policy import RepositorySecurityPolicy
from fap_repository_structured_planner import RepositoryStructuredPlanner
from fap_repository_verifier import VerificationCommand


class RepositorySecurityPolicyTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        return proc.stdout

    def _plan(self, root: Path):
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "fap-tests@example.invalid")
        self._git(root, "config", "user.name", "FAP Tests")
        (root / "calc.py").write_text("x = 1\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")
        return RepositoryStructuredPlanner(root).plan("Update calc.py implementation")

    def test_matching_plan_edit_and_python_command_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._plan(root)
            row = next(x for x in plan.files if x.path == "calc.py")
            edit = FileEdit("calc.py", "modify", row.before_sha256, "x = 2\n")
            command = VerificationCommand(
                name="tests",
                phase="focused",
                argv=(sys.executable, "-m", "unittest"),
            )
            report = RepositorySecurityPolicy(
                allowed_executables=(Path(sys.executable).name,)
            ).audit(plan=plan, edits=(edit,), commands=(command,))
            self.assertTrue(report.allowed, report.findings)

    def test_unplanned_path_and_bad_executable_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._plan(root)
            edit = FileEdit("../escape.py", "modify", "0" * 64, "x=2\n")
            command = VerificationCommand(
                name="bad",
                phase="focused",
                argv=("bash", "-lc", "echo hi"),
            )
            report = RepositorySecurityPolicy().audit(
                plan=plan,
                edits=(edit,),
                commands=(command,),
            )
            self.assertFalse(report.allowed)
            codes = {x.code for x in report.findings}
            self.assertIn("unsafe_repository_path", codes)
            self.assertIn("executable_not_allowed", codes)

    def test_write_enabled_plan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = self._plan(root)
            report = RepositorySecurityPolicy().audit(
                plan=replace(plan, write_enabled=True)
            )
            self.assertFalse(report.allowed)
            self.assertIn(
                "plan_write_enabled",
                {x.code for x in report.findings},
            )


if __name__ == "__main__":
    unittest.main()
