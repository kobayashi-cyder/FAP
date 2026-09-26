from __future__ import annotations
import json, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from fap_autonomy.v68_code_factory import V68CodeFactory


def write(p,s):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')

out={'schema':1,'mechanism_only':True}

# 1) Constrained natural-language -> TaskPlan -> generated function
with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as work:
    r=Path(src)
    write(r/'test_calc.py','import unittest\nfrom calc import score\nclass T(unittest.TestCase):\n def test_score(self): self.assertEqual(score(4,3),11)\n')
    f=V68CodeFactory(workspace_root=work,max_rounds=3)
    g=f.run(task_id='demo-nl',source_repo=src,test_command=[sys.executable,'-m','unittest','discover','-v'],
            objective='function score(x,y) = x*2+y in calc.py')
    out['natural_language_generation']={'status':g['status'],'rounds':g.get('manifest',{}).get('rounds'),'task_plan':g.get('manifest',{}).get('task_plan')}

# 2) NameError produces direct-import + qualified-reference alternatives and races them
with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as work:
    r=Path(src)
    write(r/'helper.py','def normalize(x): return x.strip().lower()\n')
    write(r/'main.py','def run(x): return normalize(x)\n')
    write(r/'test_main.py','import unittest\nfrom main import run\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(run(" A "),"a")\n')
    f=V68CodeFactory(workspace_root=work,max_rounds=3)
    g=f.run(task_id='demo-race',source_repo=src,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair repository')
    races=g.get('manifest',{}).get('races',[])
    out['candidate_race']={'status':g['status'],'rounds':g.get('manifest',{}).get('rounds'),'candidate_count':len(races[0]) if races else 0,
                           'reasons':[x.get('reason') for x in races[0]] if races else []}

# 3) TypeError signature compatibility only with explicit alias contract
with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as work:
    r=Path(src)
    write(r/'m.py','def scale(value):\n    return value*2\n')
    write(r/'test_m.py','import unittest\nfrom m import scale\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(scale(amount=3),6)\n')
    f=V68CodeFactory(workspace_root=work,max_rounds=3)
    g=f.run(task_id='demo-kw',source_repo=src,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='support amount keyword',
            structured={'mode':'repair','keyword_aliases':{'amount':'value'}})
    races=g.get('manifest',{}).get('races',[])
    out['signature_race']={'status':g['status'],'candidate_count':len(races[0]) if races else 0,'reasons':[x.get('reason') for x in races[0]] if races else []}

# 4) Mechanical compile repair
with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as work:
    r=Path(src)
    write(r/'bad.py','def f()\n    return 9\n')
    write(r/'test_bad.py','import unittest\nfrom bad import f\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(f(),9)\n')
    f=V68CodeFactory(workspace_root=work,max_rounds=3)
    g=f.run(task_id='demo-syntax',source_repo=src,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair syntax')
    out['compile_repair']={'status':g['status'],'rounds':g.get('manifest',{}).get('rounds')}

print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
(ROOT/'demo_v68_code_factory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
