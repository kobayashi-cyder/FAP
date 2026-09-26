from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from fap_repository_collab import RepositoryCodingCollaboration


class RepositoryCollaborationTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        return proc.stdout

    def _fixture(self, root: Path) -> str:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "fap-tests@example.invalid")
        self._git(root, "config", "user.name", "FAP Tests")
        (root / "calc.py").write_text(
            "def add_one(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "fixture")
        return self._git(root, "rev-parse", "HEAD").strip()

    def test_snapshot_is_serializable_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            commit = self._fixture(root)
            collab = RepositoryCodingCollaboration(root)
            snap = collab.snapshot(
                "Update calc.py implementation",
                branch="collab/coding-expansion",
                base_commit=commit,
            )

            self.assertEqual(snap.contract, "fap.repository.collab.v1")
            self.assertEqual(snap.branch, "collab/coding-expansion")
            self.assertEqual(snap.base_commit, commit)
            self.assertEqual(len(snap.plan_id), 64)
            self.assertEqual(len(snap.repository_digest), 64)
            self.assertFalse(snap.write_enabled)
            payload = snap.to_dict()
            self.assertIn("files", payload)
            rendered = repr(payload)
            self.assertNotIn("return value + 1", rendered)
            self.assertNotIn("excerpt", rendered)
            self.assertNotIn("content", rendered)

    def test_main_branch_is_rejected_for_collaboration_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            collab = RepositoryCodingCollaboration(root)
            for branch in ("main", "master"):
                with self.assertRaisesRegex(ValueError, "non-main"):
                    collab.snapshot(
                        "Update calc.py implementation",
                        branch=branch,
                    )

    def test_snapshot_tracks_explicit_create_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            collab = RepositoryCodingCollaboration(root)
            snap = collab.snapshot(
                "Update calc.py and create new file notes.md",
                branch="collab/parallel-agent",
            )
            ops = {(item.path, item.operation) for item in snap.files}
            self.assertIn(("calc.py", "modify"), ops)
            self.assertIn(("notes.md", "create"), ops)
            self.assertIn("no_direct_main_write", snap.required_checks)


if __name__ == "__main__":
    unittest.main()
