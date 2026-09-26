from pathlib import Path
import json
import tempfile
import unittest

from fap_code_generator import CodeGeneratorOrgan
from fap_v87_08_code_generator_gateway import FAPV8708


class CodeGeneratorTests(unittest.TestCase):
    def _gen(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root=Path(td.name)
        return CodeGeneratorOrgan(root/'artifacts', root/'workspace'), root

    def test_claims_python_calculator(self):
        self.assertTrue(CodeGeneratorOrgan.claims('Pythonで四則演算できる電卓を作って。'))

    def test_game_remains_game_builder(self):
        self.assertFalse(CodeGeneratorOrgan.claims('マインスイーパーを作って'))

    def test_python_calculator_generated_and_selftested(self):
        gen,root=self._gen()
        out=gen.build('Pythonで四則演算できる電卓を作って。')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'],'calculator')
        self.assertIn('self_test',out['validation']['checks'])
        p=root/'artifacts'/'fap_calculator.py'
        self.assertTrue(p.exists())
        self.assertIn('def calculate',p.read_text(encoding='utf-8'))

    def test_python_csv_stats(self):
        gen,root=self._gen()
        out=gen.build('CSVを読み込んで平均、中央値、最大値を表示するPythonスクリプトを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'],'csv_stats')
        self.assertIn('self_test',out['validation']['checks'])

    def test_html_notepad_local_storage(self):
        gen,root=self._gen()
        out=gen.build('HTMLでメモ帳を作って。入力内容をブラウザに保存して。')
        self.assertTrue(out['ok'])
        text=(root/'artifacts'/'fap_notepad.html').read_text(encoding='utf-8')
        self.assertIn('localStorage',text)
        self.assertIn('<textarea',text)

    def test_html_counter(self):
        gen,root=self._gen()
        out=gen.build('HTMLでボタンを押すと増えるカウンターを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'],'counter')

    def test_json_config(self):
        gen,root=self._gen()
        out=gen.build('JSONの設定ファイルを作って')
        self.assertTrue(out['ok'])
        data=json.loads((root/'artifacts'/'fap_generated_config.json').read_text(encoding='utf-8'))
        self.assertEqual(data['version'],'87.08')

    def test_markdown_document(self):
        gen,root=self._gen()
        out=gen.build('Markdownで仕様書を作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['language'],'markdown')

    def test_unknown_python_stays_codegen_partial(self):
        gen,root=self._gen()
        out=gen.build('Pythonコードを作って')
        self.assertFalse(out['ok'])
        self.assertIn('処理内容',out['reply'])
        self.assertFalse(out['artifacts'])

    def test_gateway_routes_codegen(self):
        core=FAPV8708()
        out=core.chat('Pythonで四則演算できる電卓を作って。','v8708-code')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')
        self.assertTrue(any(x['name']=='fap_calculator.py' for x in out['artifacts']))
        self.assertEqual(out['status']['code_generator']['stage'],1)

    def test_gateway_game_regression(self):
        core=FAPV8708()
        out=core.chat('マインスイーパーを作成してください','v8708-game')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')
        self.assertTrue(any(x['name']=='fap_minesweeper.html' for x in out['artifacts']))

    def test_repair_is_bounded(self):
        gen,root=self._gen()
        spec=gen.infer('HTMLでメモ帳を作って')
        repaired=gen.repair(spec,'<html><body>x</body>', ['HTML structure incomplete'])
        self.assertTrue(repaired.lower().startswith('<!doctype html>'))
        self.assertIn('</html>',repaired.lower())


if __name__=='__main__':
    unittest.main()
