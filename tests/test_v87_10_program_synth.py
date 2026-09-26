from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from fap_program_synth import ProgramSynthesizer
from fap_v87_10_program_synth_gateway import FAPV8710


class V8710ProgramSynthTests(unittest.TestCase):
    def _gen(self):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root = Path(td.name)
        return ProgramSynthesizer(root/'artifacts', root/'workspace'), root

    def test_extract_numbers_then_sum(self):
        gen, root = self._gen()
        out = gen.build('Pythonで文章から数字だけ抽出して合計を出すコードを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'], 'python_program_ir')
        self.assertEqual(out['program_ir']['steps'], ['extract_numbers', 'sum'])
        p = root/'artifacts'/'fap_synthesized_program.py'
        cp = subprocess.run([sys.executable, str(p), 'abc 10 x 2.5'], capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0)
        self.assertEqual(float(cp.stdout.strip()), 12.5)

    def test_clean_unique_sort_lines(self):
        gen, root = self._gen()
        out = gen.build('Pythonでテキストファイルの空行を除いて重複行を消し昇順に並べるコードを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['program_ir']['input'], 'text_file')
        self.assertEqual(out['program_ir']['steps'], ['split_lines','filter_nonempty','unique','sort'])
        src = root/'sample.txt'; src.write_text('b\n\na\nb\n', encoding='utf-8')
        p = root/'artifacts'/'fap_synthesized_program.py'
        cp = subprocess.run([sys.executable, str(p), str(src)], capture_output=True, text=True)
        self.assertEqual(json.loads(cp.stdout), ['a','b'])

    def test_json_numeric_keys(self):
        gen, root = self._gen()
        out = gen.build('PythonでJSONファイルから値が数値のキーだけ取り出すコードを作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['program_ir']['steps'], ['json_numeric_keys'])
        src = root/'sample.json'; src.write_text('{"a":1,"b":"x","c":2.5,"d":true}', encoding='utf-8')
        p = root/'artifacts'/'fap_synthesized_program.py'
        cp = subprocess.run([sys.executable, str(p), str(src)], capture_output=True, text=True)
        self.assertEqual(json.loads(cp.stdout), ['a','c'])

    def test_count_occurrences_parameterized(self):
        gen, root = self._gen()
        out = gen.build('Pythonで文章中の指定した単語の出現回数を数えるツールを作って')
        self.assertTrue(out['ok'])
        self.assertIn('count_occurrences', out['program_ir']['steps'])
        p = root/'artifacts'/'fap_synthesized_program.py'
        cp = subprocess.run([sys.executable, str(p), 'cat dog cat', '--needle', 'cat'], capture_output=True, text=True)
        self.assertEqual(cp.stdout.strip(), '2')

    def test_regex_extract_parameterized(self):
        gen, root = self._gen()
        out = gen.build('Pythonで正規表現で文字列を抽出するコードを作って')
        self.assertTrue(out['ok'])
        p = root/'artifacts'/'fap_synthesized_program.py'
        cp = subprocess.run([sys.executable, str(p), 'a12 b34', '--pattern', r'\d+'], capture_output=True, text=True)
        self.assertEqual(json.loads(cp.stdout), ['12','34'])

    def test_head_count(self):
        gen, root = self._gen()
        out = gen.build('Pythonでテキストの空行を除いて先頭2行だけ出すコードを作って')
        self.assertTrue(out['ok'])
        self.assertIn('head', out['program_ir']['steps'])
        self.assertEqual(out['program_ir']['parameters']['count'], '2')

    def test_v8709_composed_regression(self):
        gen, root = self._gen()
        out = gen.build('Pythonで数字のリストを降順に並べ替えて、合計と平均も表示するコードを作って')
        self.assertTrue(out['ok'])
        self.assertIn(out['code_spec']['target'], {'python_composed','python_program_ir'})

    def test_fixed_calculator_regression(self):
        gen, root = self._gen()
        out = gen.build('Pythonで四則演算できる電卓を作って')
        self.assertTrue(out['ok'])
        self.assertEqual(out['code_spec']['target'], 'calculator')

    def test_game_not_claimed(self):
        self.assertFalse(ProgramSynthesizer.claims('マインスイーパーを作って'))

    def test_gateway_stage3(self):
        core = FAPV8710()
        out = core.chat('Pythonで文章から数字だけ抽出して合計を出すコードを作って','v8710-a')
        self.assertEqual(out['ability'],'builder')
        self.assertEqual(out['verdict'],'OK')
        self.assertEqual(out['status']['code_generator']['stage'],3)
        self.assertTrue(any(x['name']=='fap_synthesized_program.py' for x in out['artifacts']))


if __name__ == '__main__': unittest.main()
