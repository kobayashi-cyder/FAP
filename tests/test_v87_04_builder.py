from pathlib import Path
import tempfile
import unittest

from fap_builder import ArtifactBuilder
from fap_v87_04_builder_gateway import FAPV8704
from fap_v78_distilled import DistilledFAPOrgan


class BuilderTests(unittest.TestCase):
    def test_tetris_intent_routes_builder(self):
        core = FAPV8704()
        self.assertEqual(core.intent.classify("テトリスを作成できますか？").name, "builder")

    def test_image_stays_image(self):
        core = FAPV8704()
        self.assertIn(core.intent.classify("猫の画像を作って").name, {"image_generate", "image_capability"})

    def test_tetris_build_and_validation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            b = ArtifactBuilder(root / "artifacts", root / "work")
            out = b.build("テトリスを作成してください")
            self.assertTrue(out["ok"])
            self.assertEqual(out["artifacts"][0]["name"], "fap_tetris.html")
            p = root / "artifacts" / "fap_tetris.html"
            self.assertTrue(p.exists())
            text = p.read_text(encoding="utf-8")
            self.assertIn("function collide", text)
            self.assertIn("function rotate", text)
            self.assertIn("function sweep", text)
            self.assertIn("keydown", text)

    def test_goal_completion_prefers_planning(self):
        organ = DistilledFAPOrgan()
        acts = organ.activate("途中で失敗しても、目的を達成するまでどう進める？")
        self.assertTrue(acts)
        self.assertEqual(acts[0].name, "planning")

    def test_core_builder_returns_artifact(self):
        core = FAPV8704()
        out = core.chat("テトリスを作成できますか？", "builder_test")
        self.assertEqual(out["ability"], "builder")
        self.assertEqual(out["verdict"], "OK")
        self.assertTrue(out["artifacts"])


if __name__ == "__main__":
    unittest.main()
