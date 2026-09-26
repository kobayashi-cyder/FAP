from pathlib import Path
import tempfile
import unittest

from fap_code_composer import CompositionalCodeGenerator
from fap_v87_09_compositional_codegen_gateway import FAPV8709


class V8709CompositionalTests(unittest.TestCase):
    def _gen(self):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root=Path(td.name)
        return CompositionalCodeGenerator(root/'artifacts', root/'workspace'), root

    def test_python_text_counts_compose(self):
        gen,root=self._gen()
        out=gen.build('Pythonで文章の単語数と文字数を数えるツールを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'],'python_composed')
        self.assertIn('word_count',out['code_spec']['features'])
        self.assertIn('char_count',out['code_spec']['features'])
        self.assertEqual(out['composition']['stage'],2)

    def test_python_numbers_sort_unique(self):
        gen,root=self._gen()
        out=gen.build('Pythonで数字のリストを昇順に並べ替えて重複を消すコードを作って')
        self.assertTrue(out['ok'])
        f=out['code_spec']['features']
        self.assertIn('sort',f); self.assertIn('unique',f)

    def test_python_numbers_stats_composed(self):
        gen,root=self._gen()
        out=gen.build('Pythonで数値のリストの合計と平均と最大値を表示するコードを作って')
        self.assertTrue(out['ok'])
        f=out['code_spec']['features']
        self.assertIn('sum',f); self.assertIn('mean',f); self.assertIn('max',f)

    def test_python_json_keys_types(self):
        gen,root=self._gen()
        out=gen.build('PythonでJSONファイルを読み込んでキー一覧と値の型を表示するスクリプトを作って')
        self.assertTrue(out['ok'])
        f=out['code_spec']['features']
        self.assertIn('input:json_file',f)
        self.assertIn('json_keys',f); self.assertIn('json_types',f)

    def test_html_reverse_counter_tool(self):
        gen,root=self._gen()
        out=gen.build('HTMLで入力した文章を逆順にして文字数も表示するツールを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'],'html_composed')
        text=(root/'artifacts'/'fap_composed_text_tool.html').read_text(encoding='utf-8')
        self.assertIn('reverse',text); self.assertIn('char_count',text)

    def test_html_storage_composition(self):
        gen,root=self._gen()
        out=gen.build('HTMLで文章を大文字に変換してブラウザに保存するツールを作って')
        self.assertTrue(out['ok'])
        text=(root/'artifacts'/'fap_composed_text_tool.html').read_text(encoding='utf-8')
        self.assertIn('localStorage',text)

    def test_unknown_operation_stays_partial(self):
        gen,root=self._gen()
        out=gen.build('Pythonで量子回路を最適化するコードを作って')
        self.assertFalse(out['ok'])
        self.assertIn('実行したい処理',out['reply'])

    def test_v8708_fixed_calculator_regression(self):
        gen,root=self._gen()
        out=gen.build('Pythonで四則演算できる電卓を作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'],'calculator')

    def test_game_not_claimed(self):
        self.assertFalse(CompositionalCodeGenerator.claims('マインスイーパーを作って'))

    def test_gateway_composed_codegen(self):
        core=FAPV8709()
        out=core.chat('Pythonで文章の単語数と文字数を数えるツールを作って','v8709-a')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')
        self.assertEqual(out['status']['code_generator']['stage'],2)
        self.assertTrue(any(x['name']=='fap_composed_tool.py' for x in out['artifacts']))

    def test_gateway_game_regression(self):
        core=FAPV8709()
        out=core.chat('マインスイーパーを作成してください','v8709-game')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')


if __name__=='__main__': unittest.main()
