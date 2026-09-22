from __future__ import annotations

import inspect
import os
import struct
import tempfile
import unittest
from pathlib import Path

import fap_local_image_backend as local_backend_module
from fap_local_image_backend import LocalRasterGenerator
from fap_v87_63_local_raster_gateway import FAPV8763Unified


class LocalRasterImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_renderer_generates_valid_png_without_external_api(self):
        with tempfile.TemporaryDirectory() as td:
            backend = LocalRasterGenerator(self.root, Path(td))
            out = backend.generate("犬の絵を作成して", width=256, height=256)
            self.assertTrue(out["ok"])
            self.assertTrue(out["local_raster"])
            self.assertTrue(out["structural_verified"])
            path = Path(td) / Path(out["artifacts"][0]["src"]).name
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(len(raw), 100)
            width, height = struct.unpack(">II", raw[16:24])
            self.assertEqual((width, height), (256, 256))

    def test_multiple_visual_concepts_use_same_renderer(self):
        with tempfile.TemporaryDirectory() as td:
            backend = LocalRasterGenerator(self.root, Path(td))
            dog = backend.generate("犬の画像を作って", 256, 256)
            cat = backend.generate("猫の画像を作って", 256, 256)
            tree = backend.generate("木の絵を描いて", 256, 256)
            self.assertTrue(dog["ok"])
            self.assertTrue(cat["ok"])
            self.assertTrue(tree["ok"])
            self.assertNotEqual(dog["concept_id"], cat["concept_id"])
            self.assertNotEqual(cat["concept_id"], tree["concept_id"])

    def test_unknown_visual_concept_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            backend = LocalRasterGenerator(self.root, Path(td))
            out = backend.generate("zxqvblorfの絵を作って", 256, 256)
            self.assertFalse(out["ok"])
            self.assertFalse(out["structural_verified"])

    def test_renderer_source_has_no_subject_specific_branch(self):
        source = inspect.getsource(local_backend_module)
        for forbidden in ("if dog", "if cat", "if 犬", "if 猫"):
            self.assertNotIn(forbidden, source)

    def test_latest_chat_routes_to_local_image_and_returns_artifact(self):
        old_w = os.environ.get("FAP_IMAGE_WIDTH")
        old_h = os.environ.get("FAP_IMAGE_HEIGHT")
        os.environ["FAP_IMAGE_WIDTH"] = "256"
        os.environ["FAP_IMAGE_HEIGHT"] = "256"
        try:
            core = FAPV8763Unified()
            core.image.orchestrator._external_available = lambda: (False, "offline")
            out = core.chat("犬の絵を作成して", "v8763-local-image")
        finally:
            if old_w is None:
                os.environ.pop("FAP_IMAGE_WIDTH", None)
            else:
                os.environ["FAP_IMAGE_WIDTH"] = old_w
            if old_h is None:
                os.environ.pop("FAP_IMAGE_HEIGHT", None)
            else:
                os.environ["FAP_IMAGE_HEIGHT"] = old_h

        self.assertEqual(out["verdict"], "OK")
        self.assertIn("semantic-action-resolve", out["route"])
        self.assertIn("local-raster", out["route"])
        self.assertTrue(out["artifacts"])
        self.assertEqual(out["artifacts"][0]["type"], "image")
        self.assertNotIn("AUTOMATIC1111", out["reply"])


if __name__ == "__main__":
    unittest.main()
