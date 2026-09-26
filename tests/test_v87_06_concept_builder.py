from pathlib import Path
import tempfile
import unittest

from fap_concept_builder import ConceptMechanismBuilder
from fap_v87_06_concept_builder_gateway import FAPV8706


class ConceptBuilderTests(unittest.TestCase):
    def test_minesweeper_name_resolves_and_builds(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=ConceptMechanismBuilder(root/'a',root/'w')
            spec=b.infer('マインスイーパーを作成してください')
            self.assertEqual(spec.target,'minesweeper')
            out=b.build('マインスイーパーを作成してください')
            self.assertTrue(out['ok'])
            self.assertEqual(out['build_spec']['target'],'minesweeper')
            self.assertTrue((root/'a'/'fap_minesweeper.html').exists())

    def test_minesweeper_mechanics_resolve_without_name(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=ConceptMechanismBuilder(root/'a',root/'w')
            spec=b.infer('地雷を避けて、周囲の数字を手掛かりにマスを開け、旗を置くゲームを作って')
            self.assertEqual(spec.target,'minesweeper')

    def test_2048_name_resolves_and_builds(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=ConceptMechanismBuilder(root/'a',root/'w')
            out=b.build('2048を作って')
            self.assertTrue(out['ok'])
            self.assertEqual(out['build_spec']['target'],'2048')
            self.assertTrue((root/'a'/'fap_2048.html').exists())

    def test_2048_mechanics_resolve_without_name(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=ConceptMechanismBuilder(root/'a',root/'w')
            spec=b.infer('4×4のタイルをスライドして、同じ数字を合体させるゲームを作って')
            self.assertEqual(spec.target,'2048')

    def test_memory_match_build(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=ConceptMechanismBuilder(root/'a',root/'w')
            out=b.build('神経衰弱を作成してください')
            self.assertTrue(out['ok'])
            self.assertEqual(out['build_spec']['target'],'memory_match')

    def test_unknown_game_returns_targeted_questions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=ConceptMechanismBuilder(root/'a',root/'w')
            out=b.build('ゼルパゲームを作って')
            self.assertFalse(out['ok'])
            self.assertIn('最小情報',out['reply'])
            self.assertIn('操作',out['reply'])

    def test_gateway_routes_minesweeper_to_builder(self):
        core=FAPV8706()
        self.assertEqual(core.intent.classify('マインスイーパーを作成して').name,'builder')
        out=core.chat('マインスイーパーを作成して','v8706-test')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')
        self.assertEqual(out['status']['builder']['stage'],3)
        self.assertTrue(any(x['name']=='fap_minesweeper.html' for x in out['artifacts']))

    def test_old_breakout_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            out=ConceptMechanismBuilder(root/'a',root/'w').build('ブロック崩しを作って')
            self.assertTrue(out['ok'])
            self.assertEqual(out['build_spec']['target'],'breakout')

if __name__=='__main__':
    unittest.main()
