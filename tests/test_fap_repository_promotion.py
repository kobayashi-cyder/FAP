from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_repository_executor import FileEdit
from fap_repository_planner import RepositoryPlanner
from fap_repository_promotion import PromotionApproval, VerifiedCandidatePromoter
from fap_repository_verifier import VerificationCommand


class RepositoryV8769Tests(unittest.TestCase):
    def _git(self, root: Path, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if check and proc.returncode != 0:
            raise AssertionError(proc.stdout)
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

    def _candidate(self, root: Path, replacement: str):
        original = (root / "calc.py").read_text(encoding="utf-8")
        plan = RepositoryPlanner(root, max_files=5).plan(
            "Fix calc.py implementation and run tests"
        )
        target = next(x for x in plan.files if x.path == "calc.py")
        edit = FileEdit(
            path="calc.py",
            operation="modify",
            before_sha256=target.before_sha256,
            content=original.replace("value + 1", replacement),
        )
        return original, plan, edit

    def test_verified_candidate_creates_local_branch_without_moving_head(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            original, plan, edit = self._candidate(root, "int(value) + 1")
            base = self._git(root, "rev-parse", "HEAD").strip()
            approval = PromotionApproval(
                plan_id=plan.plan_id,
                expected_base_commit=base,
                allow_candidate_branch=True,
                reason="verified repository coding candidate",
            )

            report = VerifiedCandidatePromoter(root).promote(
                plan,
                (edit,),
                self._commands(),
                approval,
            )

            self.assertEqual(report.state, "candidate_branch_created")
            self.assertIsNotNone(report.branch)
            self.assertIsNotNone(report.commit_sha)
            self.assertEqual(report.base_commit, base)
            self.assertEqual(
                self._git(root, "rev-parse", "HEAD").strip(),
                base,
            )
            self.assertEqual(
                (root / "calc.py").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(self._git(root, "status", "--porcelain"), "")
            self.assertEqual(
                self._git(root, "rev-parse", report.branch or "").strip(),
                report.commit_sha,
            )
            candidate_source = self._git(
                root, "show", f"{report.branch}:calc.py"
            )
            self.assertIn("int(value) + 1", candidate_source)
            parent = self._git(
                root, "rev-parse", f"{report.commit_sha}^"
            ).strip()
            self.assertEqual(parent, base)

    def test_gate_rejects_without_explicit_branch_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            _, plan, edit = self._candidate(root, "int(value) + 1")
            base = self._git(root, "rev-parse", "HEAD").strip()

            report = VerifiedCandidatePromoter(root).promote(
                plan,
                (edit,),
                self._commands(),
                PromotionApproval(
                    plan_id=plan.plan_id,
                    expected_base_commit=base,
                    allow_candidate_branch=False,
                    reason="not approved",
                ),
            )

            self.assertEqual(report.state, "rejected")
            self.assertTrue(any("candidate branch creation not approved" in x for x in report.errors))
            self.assertEqual(self._git(root, "branch", "--list", "fap/candidate/*"), "")

    def test_gate_rejects_base_commit_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            _, plan, edit = self._candidate(root, "int(value) + 1")

            report = VerifiedCandidatePromoter(root).promote(
                plan,
                (edit,),
                self._commands(),
                PromotionApproval(
                    plan_id=plan.plan_id,
                    expected_base_commit="0" * 40,
                    allow_candidate_branch=True,
                    reason="stale approval",
                ),
            )

            self.assertEqual(report.state, "rejected")
            self.assertIn("base_commit_mismatch", report.errors)
            self.assertEqual(self._git(root, "branch", "--list", "fap/candidate/*"), "")

    def test_failing_verification_never_creates_candidate_branch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            _, plan, edit = self._candidate(root, "value + 2")
            base = self._git(root, "rev-parse", "HEAD").strip()

            report = VerifiedCandidatePromoter(root).promote(
                plan,
                (edit,),
                self._commands(),
                PromotionApproval(
                    plan_id=plan.plan_id,
                    expected_base_commit=base,
                    allow_candidate_branch=True,
                    reason="must pass tests",
                ),
            )

            self.assertEqual(report.state, "rejected")
            self.assertIsNotNone(report.verification)
            self.assertEqual(report.verification.state, "rejected")
            self.assertEqual(self._git(root, "branch", "--list", "fap/candidate/*"), "")

    def test_candidate_branch_collision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            _, plan, edit = self._candidate(root, "int(value) + 1")
            base = self._git(root, "rev-parse", "HEAD").strip()
            approval = PromotionApproval(
                plan_id=plan.plan_id,
                expected_base_commit=base,
                allow_candidate_branch=True,
                reason="single deterministic candidate ref",
            )
            promoter = VerifiedCandidatePromoter(root)

            first = promoter.promote(plan, (edit,), self._commands(), approval)
            second = promoter.promote(plan, (edit,), self._commands(), approval)

            self.assertEqual(first.state, "candidate_branch_created")
            self.assertEqual(second.state, "rejected")
            self.assertTrue(
                any(x.startswith("candidate_branch_already_exists:") for x in second.errors)
            )
            self.assertEqual(
                self._git(root, "rev-parse", first.branch or "").strip(),
                first.commit_sha,
            )


if __name__ == "__main__":
    unittest.main()
