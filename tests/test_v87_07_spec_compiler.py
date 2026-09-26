from pathlib import Path
import tempfile
import unittest

from fap_spec_builder import SpecificationCompilerBuilder
from fap_v87_07_spec_compiler_gateway import FAPV8707

PROMPT = '''6×6の盤面で緑の駒を上下左右に動かすゲームを作って。
星を5個集めたら勝ち。
3回動くたびに赤い障害物の位置をランダムに変える。
赤い障害物に触れたら負け。
スマホのボタンで操作できて、再スタートもできるようにして。'''


class SpecificationCompilerTests(unittest.TestCase):
    def test_complete_prompt_compiles_without_questions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=SpecificationCompilerBuilder(root/'a',root/'w')
            spec=b.compile_spec(PROMPT)
            self.assertFalse(spec.missing)
            self.assertEqual((spec.rows,spec.cols),(6,6))
            self.assertEqual(spec.collectible_target,5)
            self.assertEqual(spec.hazard_relocate_every,3)
            self.assertEqual(spec.controls,'touch_dpad')
            self.assertTrue(spec.restart)
            self.assertTrue(spec.lose_on_hazard_contact)

    def test_complete_prompt_builds_new_game(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=SpecificationCompilerBuilder(root/'a',root/'w')
            out=b.build(PROMPT)
            self.assertTrue(out['ok'])
            self.assertEqual(out['artifacts'][0]['name'],'fap_compiled_grid_game.html')
            self.assertEqual(out['compiled_spec']['rows'],6)
            text=(root/'a'/'fap_compiled_grid_game.html').read_text(encoding='utf-8')
            self.assertIn('const ROWS=6',text)
            self.assertIn('const COLS=6',text)
            self.assertIn('const TARGET=5',text)
            self.assertIn('const RELOCATE_EVERY=3',text)
            self.assertIn('data-dir="up"',text)

    def test_does_not_reask_information_already_present(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=SpecificationCompilerBuilder(root/'a',root/'w').build(PROMPT)
            self.assertTrue(out['ok'])
            self.assertNotIn('盤面サイズ',out['reply'])
            self.assertNotIn('操作方法',out['reply'])

    def test_partial_prompt_asks_only_missing_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=SpecificationCompilerBuilder(root/'a',root/'w')
            out=b.build('8×8の盤面で青い駒を上下左右に動かすゲームを作って。スマホのボタンで操作する。')
            self.assertFalse(out['ok'])
            self.assertIn('勝利条件',out['reply'])
            self.assertIn('失敗要因',out['reply'])
            self.assertNotIn('盤面サイズ',out['reply'])
            self.assertNotIn('移動方法',out['reply'])
            self.assertNotIn('操作方法',out['reply'])

    def test_gateway_routes_and_builds(self):
        core=FAPV8707()
        self.assertEqual(core.intent.classify(PROMPT).name,'builder')
        out=core.chat(PROMPT,'v8707-test')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')
        self.assertEqual(out['status']['builder']['stage'],4)
        self.assertTrue(any(x['name']=='fap_compiled_grid_game.html' for x in out['artifacts']))

    def test_minesweeper_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=SpecificationCompilerBuilder(root/'a',root/'w').build('マインスイーパーを作成してください')
            self.assertTrue(out['ok'])
            self.assertEqual(out['build_spec']['target'],'minesweeper')

    def test_breakout_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=SpecificationCompilerBuilder(root/'a',root/'w').build('ブロック崩しを作って')
            self.assertTrue(out['ok'])
            self.assertEqual(out['build_spec']['target'],'breakout')

    def test_unknown_sparse_game_stays_builder_partial(self):
        core=FAPV8707()
        out=core.chat('ゼルパゲームを作って','v8707-unknown')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'PARTIAL')
        self.assertFalse(out['artifacts'])


if __name__=='__main__':
    unittest.main()
