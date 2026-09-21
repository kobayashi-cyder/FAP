from pathlib import Path
import tempfile
import unittest

from fap_generic_builder import GenericCompositionBuilder
from fap_v87_05_generic_builder_gateway import FAPV8705


class GenericBuilderTests(unittest.TestCase):
    def test_breakout_intent_is_builder(self):
        core = FAPV8705()
        self.assertEqual(core.intent.classify("ブロック崩しを作成してください").name, "builder")

    def test_unknown_create_stays_builder(self):
        core = FAPV8705()
        self.assertEqual(core.intent.classify("謎の装置を作成してください").name, "builder")
        out = core.chat("謎の装置を作成してください", "unknown-build")
        self.assertEqual(out["ability"], "builder")
        self.assertEqual(out["verdict"], "PARTIAL")
        self.assertIn("不足", out["reply"])

    def test_breakout_build(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=GenericCompositionBuilder(root/"artifacts", root/"work")
            out=b.build("ブロック崩しを作成してください")
            self.assertTrue(out["ok"])
            self.assertEqual(out["build_spec"]["target"], "breakout")
            p=root/"artifacts"/"fap_breakout.html"
            self.assertTrue(p.exists())
            text=p.read_text(encoding="utf-8")
            self.assertIn("const bricks", text)
            self.assertIn("function resetBall", text)
            self.assertIn("paddle", text)

    def test_mechanic_first_breakout(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=GenericCompositionBuilder(root/"artifacts", root/"work")
            spec=b.infer("ボールをパドルで打ってブロックを消すゲームを作って")
            self.assertEqual(spec.target,"breakout")

    def test_pong_build(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=GenericCompositionBuilder(root/"a",root/"w").build("PONGゲームを作って")
            self.assertTrue(out["ok"])
            self.assertEqual(out["build_spec"]["target"],"pong")

    def test_snake_build(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=GenericCompositionBuilder(root/"a",root/"w").build("スネークゲームを作成して")
            self.assertTrue(out["ok"])
            self.assertEqual(out["build_spec"]["target"],"snake")

    def test_tetris_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=GenericCompositionBuilder(root/"a",root/"w").build("テトリスを作って")
            self.assertTrue(out["ok"])
            self.assertEqual(out["artifacts"][0]["name"],"fap_tetris.html")


if __name__ == "__main__":
    unittest.main()
