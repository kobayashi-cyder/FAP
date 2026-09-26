from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_plan_quality import RepositoryPlanQualityGate
from fap_repository_structured_planner import RepositoryStructuredPlanner


class RepositoryPlanQualityGateTests(unittest.TestCase):
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
        (root / "calc.py").write_text(
            "def add(a,b):\n    return a+b\n",
            encoding="utf-8",
        )
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")

    def test_ready_structured_plan_passes_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update calc.py implementation"
            )
            report = RepositoryPlanQualityGate().assess(plan)
            self.assertTrue(report.acceptable, report.issues)
            self.assertEqual(report.mutation_count, 1)

    def test_missing_regression_and_python_checks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update calc.py implementation"
            )
            broken = replace(
                plan,
                required_checks=tuple(
                    x for x in plan.required_checks
                    if x not in {
                        "regression_tests",
                        "python_compile",
                        "focused_tests",
                    }
                ),
            )
            report = RepositoryPlanQualityGate().assess(broken)
            self.assertFalse(report.acceptable)
            codes = {issue.code for issue in report.issues}
            self.assertIn("missing_regression_tests", codes)
            self.assertIn("missing_python_compile", codes)
            self.assertIn("missing_focused_tests", codes)

    def test_write_enabled_and_invalid_plan_id_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryStructuredPlanner(root).plan(
                "Update calc.py implementation"
            )
            broken = replace(
                plan,
                write_enabled=True,
                plan_id="bad",
            )
            report = RepositoryPlanQualityGate().assess(broken)
            codes = {issue.code for issue in report.issues}
            self.assertFalse(report.acceptable)
            self.assertIn("plan_write_enabled", codes)
            self.assertIn("invalid_plan_id", codes)

    def test_non_ready_plan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            plan = RepositoryStructuredPlanner(root).plan("Update missing.py")
            report = RepositoryPlanQualityGate().assess(plan)
            self.assertFalse(report.acceptable)
            self.assertIn("plan_not_ready", {x.code for x in report.issues})


if __name__ == "__main__":
    unittest.main()
