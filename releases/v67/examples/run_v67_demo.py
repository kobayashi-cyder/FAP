from __future__ import annotations
import json, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from fap_autonomy.repository_code_factory import NativeRepositoryCodeFactory


def write(p,s):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')

with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as work:
    r=Path(src)
    write(r/'helpers.py','def inc(x): return x+1\ndef double(x): return x*2\n')
    write(r/'one.py','def one(x): return inc(x)\n')
    write(r/'two.py','def two(x): return double(x)\n')
    write(r/'test_repo.py','import unittest\nfrom one import one\nfrom two import two\nclass T(unittest.TestCase):\n def test_one(self): self.assertEqual(one(2),3)\n def test_two(self): self.assertEqual(two(3),6)\n')
    factory=NativeRepositoryCodeFactory(workspace_root=work,max_rounds=4)
    repair=factory.run(task_id='demo-repair',source_repo=src,
                       test_command=[sys.executable,'-m','unittest','discover','-v'],
                       objective='repair repository missing imports')

with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as work:
    r=Path(src)
    write(r/'test_calc.py','import unittest\nfrom calc import score\nclass T(unittest.TestCase):\n def test_score(self): self.assertEqual(score(4,3),11)\n')
    ir={
      'target_path':'calc.py',
      'function_spec':{
        'name':'score','args':['x','y'],
        'expression':{'add':[{'mul':[{'var':'x'},2]},{'var':'y'}]},
        'doc':'Deterministic generated function from V67 safe Code IR.'
      }
    }
    factory=NativeRepositoryCodeFactory(workspace_root=work,max_rounds=2)
    generated=factory.run(task_id='demo-generate',source_repo=src,
                          test_command=[sys.executable,'-m','unittest','discover','-v'],
                          objective='generate score function',initial_generation=ir)

out={
 'schema':1,
 'mechanism_only':True,
 'repair':{
   'status':repair['status'],
   'rounds':repair.get('manifest',{}).get('rounds'),
   'patch_count':len(repair.get('manifest',{}).get('patches',[])),
   'lineage_valid':repair.get('manifest',{}).get('lineage_valid'),
 },
 'generation':{
   'status':generated['status'],
   'rounds':generated.get('manifest',{}).get('rounds'),
   'patch_count':len(generated.get('manifest',{}).get('patches',[])),
   'lineage_valid':generated.get('manifest',{}).get('lineage_valid'),
 },
}
print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
(ROOT/'demo_v67_code_factory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
