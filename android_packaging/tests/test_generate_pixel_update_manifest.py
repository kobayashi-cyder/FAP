from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from android_packaging.generate_pixel_update_manifest import generate


class PixelUpdateManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "knowledge").mkdir()
        (self.root / "fap_1x_standard_runtime.py").write_text(
            "from fap_dep import VALUE\nVALUE2 = VALUE\n",
            encoding="utf-8",
        )
        (self.root / "fap_dep.py").write_text("VALUE = 7\n", encoding="utf-8")
        (self.root / "knowledge" / "a.jsonl").write_text(
            '{"kind":"test","value":1}\n',
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_flattens_full_runtime_and_knowledge(self):
        manifest = generate(self.root, "a" * 40)
        self.assertEqual(manifest["schema"], "fap.pixel.runtime.manifest.v1")
        self.assertEqual(manifest["source_commit"], "a" * 40)
        self.assertEqual(manifest["entrypoint"], "fap_1x_standard_runtime.py")
        self.assertEqual(manifest["file_count"], 3)
        paths = [row["path"] for row in manifest["files"]]
        self.assertEqual(
            paths,
            [
                "fap_1x_standard_runtime.py",
                "fap_dep.py",
                "knowledge/a.jsonl",
            ],
        )
        self.assertEqual(
            manifest["total_bytes"],
            sum(row["bytes"] for row in manifest["files"]),
        )
        self.assertTrue(all(len(row["sha256"]) == 64 for row in manifest["files"]))

    def test_invalid_source_commit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "40-character"):
            generate(self.root, "main")


if __name__ == "__main__":
    unittest.main()
