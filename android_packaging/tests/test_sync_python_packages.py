from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android_packaging"))

from sync_python_packages import PackagingError, sync_packages


class SyncPythonPackagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.dest = self.base / "python"
        self.repo.mkdir()
        self.dest.mkdir()
        self.manifest = self.repo / "packages.json"
        self.report = self.base / "report.json"

    def tearDown(self):
        self.tmp.cleanup()

    def package(self, rel: str, text: str = "VALUE = 1\n") -> Path:
        path = self.repo / rel
        path.mkdir(parents=True)
        (path / "__init__.py").write_text(text, encoding="utf-8")
        return path

    def write_manifest(self, packages):
        self.manifest.write_text(
            json.dumps({"schema": 1, "packages": packages}),
            encoding="utf-8",
        )

    def sync(self):
        return sync_packages(
            repo_root=self.repo,
            destination_root=self.dest,
            manifest_path=self.manifest,
            report_path=self.report,
        )

    def test_sync_copies_packages_and_writes_deterministic_report(self):
        self.package("releases/v1/pkg_a")
        self.package("releases/v2/pkg_b", "VALUE = 2\n")
        self.write_manifest([
            {"source": "releases/v1/pkg_a", "destination": "pkg_a"},
            {"source": "releases/v2/pkg_b", "destination": "pkg_b"},
        ])
        first = self.sync()
        first_bytes = self.report.read_bytes()
        second = self.sync()
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, self.report.read_bytes())
        self.assertTrue((self.dest / "pkg_a" / "__init__.py").is_file())
        self.assertTrue((self.dest / "pkg_b" / "__init__.py").is_file())
        self.assertEqual(len(first["packages"]), 2)

    def test_stale_destination_is_replaced(self):
        self.package("src/pkg")
        stale = self.dest / "pkg"
        stale.mkdir()
        (stale / "stale.py").write_text("stale", encoding="utf-8")
        self.write_manifest([{"source": "src/pkg", "destination": "pkg"}])
        self.sync()
        self.assertFalse((stale / "stale.py").exists())
        self.assertTrue((stale / "__init__.py").exists())

    def test_missing_source_rejected_before_destination_mutation(self):
        marker = self.dest / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        self.write_manifest([{"source": "missing/pkg", "destination": "pkg"}])
        with self.assertRaises(PackagingError):
            self.sync()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_duplicate_destination_rejected(self):
        self.package("a/pkg")
        self.package("b/pkg")
        self.write_manifest([
            {"source": "a/pkg", "destination": "same"},
            {"source": "b/pkg", "destination": "same"},
        ])
        with self.assertRaisesRegex(PackagingError, "duplicate package destination"):
            self.sync()

    def test_source_escape_rejected(self):
        self.write_manifest([{"source": "../outside", "destination": "pkg"}])
        with self.assertRaises(PackagingError):
            self.sync()

    def test_missing_init_rejected(self):
        path = self.repo / "src/pkg"
        path.mkdir(parents=True)
        self.write_manifest([{"source": "src/pkg", "destination": "pkg"}])
        with self.assertRaisesRegex(PackagingError, "missing __init__"):
            self.sync()

    def test_symlink_inside_package_rejected(self):
        pkg = self.package("src/pkg")
        target = self.repo / "target.txt"
        target.write_text("secret", encoding="utf-8")
        link = pkg / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        self.write_manifest([{"source": "src/pkg", "destination": "pkg"}])
        with self.assertRaisesRegex(PackagingError, "symlink"):
            self.sync()

    def test_invalid_destination_rejected(self):
        self.package("src/pkg")
        self.write_manifest([{"source": "src/pkg", "destination": "../pkg"}])
        with self.assertRaisesRegex(PackagingError, "Python package identifier"):
            self.sync()


if __name__ == "__main__":
    unittest.main()
