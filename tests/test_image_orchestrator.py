from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fap_image_orchestrator import ImageRequestParser, ImageOrchestrator


PNG_1X1 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
).decode("ascii")


class FakeAPI:
    def __init__(self, captions):
        self.captions = list(captions)
        self.txt_calls = []
        self.interrogate_calls = 0

    def __call__(self, url, method="GET", data=None, timeout=12.0):
        if url.endswith("/sdapi/v1/sd-models"):
            return [{"title": "mock"}]
        if url.endswith("/sdapi/v1/txt2img"):
            self.txt_calls.append(dict(data or {}))
            return {"images": [PNG_1X1]}
        if url.endswith("/sdapi/v1/interrogate"):
            self.interrogate_calls += 1
            if not self.captions:
                return {"caption": ""}
            return {"caption": self.captions.pop(0)}
        raise RuntimeError(url)


class ImageOrchestratorTests(unittest.TestCase):
    def test_parser_extracts_photo_beagle_scene(self):
        spec = ImageRequestParser().parse(
            "ビーグル犬1匹の全身を写真風で、夕暮れの湖と山を背景に生成して"
        )
        self.assertEqual(spec.subjects, ("beagle",))
        self.assertEqual(spec.count, 1)
        self.assertEqual(spec.style, "photorealistic")
        self.assertEqual(spec.framing, "full-body")
        self.assertEqual(spec.lighting, "golden-hour")
        self.assertIn("lake", spec.backgrounds)
        self.assertIn("mountains", spec.backgrounds)
        self.assertTrue(spec.photorealistic)

    def test_multi_subject_scene_does_not_apply_global_single_count(self):
        spec = ImageRequestParser().parse(
            "女性1人とビーグル1匹が夕暮れの湖畔にいる写真風の画像を生成して"
        )
        self.assertIn("woman", spec.subjects)
        self.assertIn("beagle", spec.subjects)
        self.assertIsNone(spec.count)
        self.assertNotIn("multiple subjects", spec.must_not_have)

    def test_generate_repairs_missing_breed_then_selects_better_candidate(self):
        api = FakeAPI([
            "a realistic dog outdoors at sunset",
            "a photorealistic full body beagle beside a lake with mountains at golden sunset",
        ])
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {
                "FAP_IMAGE_CANDIDATES": "1",
                "FAP_IMAGE_ROUNDS": "2",
                "FAP_IMAGE_PASS_SCORE": "0.80",
            },
            clear=False,
        ):
            orch = ImageOrchestrator(
                image_base="http://mock",
                artifact_dir=Path(td),
                http_json=api,
            )
            out = orch.generate(
                "ビーグル犬1匹の全身を写真風で、夕暮れの湖と山を背景に生成して"
            )
            self.assertTrue(out["ok"])
            self.assertTrue(out["image_orchestrated"])
            self.assertTrue(out["visual_verified"])
            self.assertGreaterEqual(out["image_score"], 0.80)
            self.assertEqual(out["generation_rounds"], 2)
            self.assertEqual(len(api.txt_calls), 2)
            self.assertIn("clearly show beagle", api.txt_calls[1]["prompt"])
            self.assertTrue(Path(td, out["artifacts"][0]["name"]).exists())

    def test_generation_succeeds_but_marks_visual_unverified_without_interrogator(self):
        class NoInterrogate(FakeAPI):
            def __call__(self, url, method="GET", data=None, timeout=12.0):
                if url.endswith("/sdapi/v1/interrogate"):
                    raise RuntimeError("interrogate unavailable")
                return super().__call__(url, method=method, data=data, timeout=timeout)

        api = NoInterrogate([])
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ,
            {"FAP_IMAGE_CANDIDATES": "1", "FAP_IMAGE_ROUNDS": "1"},
            clear=False,
        ):
            orch = ImageOrchestrator(
                image_base="http://mock",
                artifact_dir=Path(td),
                http_json=api,
            )
            out = orch.generate("ビーグル犬の写真を生成して")
            self.assertTrue(out["ok"])
            self.assertFalse(out["visual_verified"])
            self.assertEqual(out["image_score"], 0.55)


if __name__ == "__main__":
    unittest.main()
