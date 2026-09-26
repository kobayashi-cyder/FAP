from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fap_media_policy import (
    ArtifactBudget,
    enhance_prompt,
    image_dimensions,
    image_profile,
    quality_mode,
    strip_control_directives,
    video_profile,
)


class MediaPolicyTests(unittest.TestCase):
    def test_quality_directive_selects_profiles(self):
        self.assertEqual(quality_mode("[FAP_MEDIA quality=draft] 画像生成: 猫"), "draft")
        self.assertEqual(quality_mode("[FAP_MEDIA quality=standard] 動画生成: 猫"), "standard")
        self.assertEqual(quality_mode("[FAP_MEDIA quality=high] 画像生成: 猫"), "high")
        self.assertEqual(image_profile("[FAP_MEDIA quality=high] x").width, 1024)
        self.assertEqual(video_profile("[FAP_MEDIA quality=high] x").keyframes, 6)

    def test_aspect_ratio_and_prompt_enrichment(self):
        profile = image_profile("[FAP_MEDIA quality=high] 16:9 浮遊都市")
        width, height = image_dimensions("16:9 浮遊都市", profile)
        self.assertEqual(width, 1024)
        self.assertLess(height, width)
        prompt = enhance_prompt(
            "[FAP_MEDIA quality=high] 浮遊都市",
            profile,
        )
        self.assertNotIn("FAP_MEDIA", prompt)
        self.assertIn("coherent composition", prompt)

    def test_control_directive_does_not_leak_to_prompt(self):
        cleaned = strip_control_directives(
            "[FAP_MEDIA quality=high] 画像生成: 白い浮遊都市"
        )
        self.assertNotIn("FAP_MEDIA", cleaned)
        self.assertIn("白い浮遊都市", cleaned)

    def test_artifact_budget_prunes_old_files_but_keeps_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for index in range(8):
                path = root / f"{index}.bin"
                path.write_bytes(bytes([index]) * 1024)
                os.utime(path, (1000 + index, 1000 + index))
                paths.append(path)

            budget = ArtifactBudget(root, max_files=4, max_bytes=6 * 1024)
            report = budget.prune([paths[0]])
            remaining = {p.name for p in root.iterdir() if p.is_file()}
            self.assertIn(paths[0].name, remaining)
            self.assertLessEqual(len(remaining), 5)
            self.assertGreater(report["removed_files"], 0)


if __name__ == "__main__":
    unittest.main()
