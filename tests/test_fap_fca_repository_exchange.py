from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fap_fca_repository_exchange import (
    CAPABILITY,
    SCHEMA,
    build_repository_evidence_capsule,
    capsule_json,
    validate_repository_evidence_capsule,
)
from fap_repository_agent import RepositoryCodingCoordinator
from fap_repository_executor import FileEdit
from fap_repository_verifier import VerificationCommand


class FAPFCARepositoryExchangeTests(unittest.TestCase):
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

    def _verified_result(self, root: Path):
        original = (root / "calc.py").read_text(encoding="utf-8")
        coordinator = RepositoryCodingCoordinator(root)

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

        return coordinator.run(
            "Fix calc.py implementation and run tests",
            proposer,
            self._commands(),
        )

    def test_verified_result_exports_inert_fca_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            result = self._verified_result(root)

            capsule = build_repository_evidence_capsule(
                result,
                source_commit="a" * 40,
            )

            self.assertEqual(capsule["schema"], SCHEMA)
            self.assertEqual(capsule["source_project"], "FAP")
            self.assertEqual(capsule["capability"], CAPABILITY)
            self.assertEqual(capsule["evidence"]["status"], "verified_candidate")
            self.assertEqual(
                capsule["mechanism"]["plan_id"],
                result.plan.plan_id,
            )
            self.assertEqual(
                capsule["mechanism"]["repository_digest"],
                result.plan.task.repository_digest,
            )

            body = dict(capsule)
            supplied = body.pop("digest")
            calculated = sha256(
                json.dumps(
                    body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(supplied, calculated)

            text = capsule_json(capsule)
            self.assertNotIn("int(value) + 1", text)
            self.assertNotIn("Fix calc.py implementation and run tests", text)
            for forbidden in ('"content"', '"replacement"', '"excerpt"', '"diff"', '"argv"', '"output"'):
                self.assertNotIn(forbidden, text)

    def test_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            capsule = build_repository_evidence_capsule(
                self._verified_result(root),
                source_commit="b" * 40,
            )
            capsule["evidence"]["repairs_used"] = 99

            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                validate_repository_evidence_capsule(capsule)

    def test_rejected_result_cannot_be_exported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            coordinator = RepositoryCodingCoordinator(root)

            def proposer(plan, context):
                raise RuntimeError("no proposal")

            rejected = coordinator.run(
                "Fix calc.py implementation and run tests",
                proposer,
                self._commands(),
            )
            self.assertEqual(rejected.state, "rejected")

            with self.assertRaisesRegex(ValueError, "only verified"):
                build_repository_evidence_capsule(
                    rejected,
                    source_commit="c" * 40,
                )

    def test_forbidden_payload_key_is_rejected_even_with_valid_digest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            capsule = build_repository_evidence_capsule(
                self._verified_result(root),
                source_commit="d" * 40,
            )
            capsule["mechanism"]["content"] = "should never cross project"
            body = dict(capsule)
            body.pop("digest", None)
            capsule["digest"] = sha256(
                json.dumps(
                    body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()

            with self.assertRaisesRegex(ValueError, "forbidden"):
                validate_repository_evidence_capsule(capsule)


if __name__ == "__main__":
    unittest.main()
