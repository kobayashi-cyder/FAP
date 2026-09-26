import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.ast_patch_planner import append_function_patch, qualified_name_patch, reexport_symbol_patch, keyword_compatibility_patches, ASTPatchError
from fap_autonomy.candidate_race import CandidateRace
from fap_autonomy.diagnostic_repair import DiagnosticRepairPlanner
from fap_autonomy.patch_engine import RepositoryPatchApplier, PatchSet, FilePatch
from fap_autonomy.repo_context import RepositoryContextBuilder
from fap_autonomy.repository_code_factory import LocalValidationRunner, digest_tree
from fap_autonomy.task_planner import NaturalLanguageTaskPlanner, TaskPlanError, expression_text_to_ir
from fap_autonomy.v68_code_factory import V68CodeFactory
from fap_autonomy.v68_coordinator import V68CodeFactoryCoordinator


def write(p, s):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding='utf-8')


class Outbox:
    def __init__(self): self.rows=[]
    def publish_candidate_manifest(self, **kw): self.rows.append(kw); return {'written':True, **kw}


class V68Tests(unittest.TestCase):
    def test_01_expression_add(self):
        self.assertEqual(expression_text_to_ir('a+b',['a','b']), {'add':[{'var':'a'},{'var':'b'}]})

    def test_02_expression_nested(self):
        x=expression_text_to_ir('a+b*2',['a','b']); self.assertIn('add',x); self.assertIn('mul',x['add'][1])

    def test_03_expression_compare(self):
        self.assertEqual(expression_text_to_ir('a>=b',['a','b']), {'ge':[{'var':'a'},{'var':'b'}]})

    def test_04_expression_if(self):
        x=expression_text_to_ir('a if a>b else b',['a','b']); self.assertIn('if',x)

    def test_05_expression_pure_call(self):
        x=expression_text_to_ir('abs(a)',['a']); self.assertEqual(x['call']['fn'],'abs')

    def test_06_expression_arbitrary_call_rejected(self):
        with self.assertRaises(TaskPlanError): expression_text_to_ir('eval(a)',['a'])

    def test_07_expression_unknown_var_rejected(self):
        with self.assertRaises(TaskPlanError): expression_text_to_ir('a+c',['a'])

    def test_08_nl_function_plan_english(self):
        p=NaturalLanguageTaskPlanner().plan(objective='function add(a,b) = a+b in calc.py')
        self.assertEqual((p.mode,p.target_path,p.function_spec['name']),('create_function','calc.py','add'))

    def test_09_nl_function_plan_japanese(self):
        p=NaturalLanguageTaskPlanner().plan(objective='関数 add(a,b) = a+b ファイル calc.py')
        self.assertEqual(p.target_path,'calc.py')

    def test_10_nl_unknown_becomes_repair(self):
        p=NaturalLanguageTaskPlanner().plan(objective='fix the failing repository')
        self.assertEqual(p.mode,'repair')

    def test_11_structured_create(self):
        p=NaturalLanguageTaskPlanner().plan(objective='x',structured={'mode':'create_function','target_path':'a.py','function_spec':{'name':'f','args':[],'expression':1}})
        self.assertEqual(p.source,'structured')

    def test_12_structured_bad_mode(self):
        with self.assertRaises(TaskPlanError): NaturalLanguageTaskPlanner().plan(objective='x',structured={'mode':'shell'})

    def test_13_append_new_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=append_function_patch(workspace=d,target_path='calc.py',function_spec={'name':'add','args':['a','b'],'expression':{'add':[{'var':'a'},{'var':'b'}]}})
            RepositoryPatchApplier(d).apply(p); ns={};exec(Path(d,'calc.py').read_text(),ns);self.assertEqual(ns['add'](2,3),5)

    def test_14_append_existing_module(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d,'calc.py'),'PI=3\n')
            p=append_function_patch(workspace=d,target_path='calc.py',function_spec={'name':'one','args':[],'expression':1})
            RepositoryPatchApplier(d).apply(p); txt=Path(d,'calc.py').read_text();self.assertIn('PI=3',txt);self.assertIn('def one',txt)

    def test_15_append_duplicate_symbol_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d,'x.py'),'def f(): return 1\n')
            with self.assertRaises(ASTPatchError): append_function_patch(workspace=d,target_path='x.py',function_spec={'name':'f','args':[],'expression':2})

    def test_16_qualified_patch(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d,'helper.py'),'def f(x): return x+1\n');write(Path(d,'main.py'),'def g(x): return f(x)\n')
            p=qualified_name_patch(workspace=d,target_path='main.py',symbol='f',module='helper');RepositoryPatchApplier(d).apply(p)
            self.assertIn('helper.f',Path(d,'main.py').read_text())

    def test_17_reexport_patch(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d,'impl.py'),'def f(): return 1\n');write(Path(d,'api.py'),'X=1\n')
            p=reexport_symbol_patch(workspace=d,target_path='api.py',symbol='f',source_module='impl');RepositoryPatchApplier(d).apply(p)
            self.assertIn('from impl import f',Path(d,'api.py').read_text())

    def test_18_keyword_variants_require_contract(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d,'m.py'),'def f(value):\n    return value+1\n')
            self.assertEqual(keyword_compatibility_patches(workspace=d,target_path='m.py',function_name='f',unexpected_keyword='amount',aliases={}),[])

    def test_19_keyword_variants_two(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d,'m.py'),'def f(value):\n    return value+1\n')
            ps=keyword_compatibility_patches(workspace=d,target_path='m.py',function_name='f',unexpected_keyword='amount',aliases={'amount':'value'})
            self.assertEqual(len(ps),2)

    def test_20_nameerror_candidates_multiple(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'helper.py','def f(x): return x+1\n');write(r/'main.py','def g(x): return f(x)\n')
            c=RepositoryContextBuilder().build(d);failure=f'  File "{r/"main.py"}", line 1, in g\nNameError: name \'f\' is not defined'
            ps=DiagnosticRepairPlanner().candidates(workspace=d,context=c,failure_text=failure);self.assertEqual(len(ps),2)

    def test_21_attributeerror_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'impl.py','def f(): return 1\n');write(r/'api.py','X=1\n');c=RepositoryContextBuilder().build(d)
            ps=DiagnosticRepairPlanner().candidates(workspace=d,context=c,failure_text="AttributeError: module 'api' has no attribute 'f'")
            self.assertEqual(len(ps),1);self.assertEqual(ps[0].reason,'reexport:f')

    def test_22_importerror_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'impl.py','def f(): return 1\n');write(r/'api.py','X=1\n');c=RepositoryContextBuilder().build(d)
            ps=DiagnosticRepairPlanner().candidates(workspace=d,context=c,failure_text="ImportError: cannot import name 'f' from 'api' (/tmp/api.py)")
            self.assertEqual(len(ps),1)

    def test_23_candidate_race_picks_passing(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'x.py','VALUE=0\n');write(r/'test_x.py','import unittest\nimport x\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(x.VALUE,2)\n')
            bad=PatchSet('bad',(FilePatch('x.py','VALUE=1\n'),));good=PatchSet('good',(FilePatch('x.py','VALUE=2\n'),))
            race=CandidateRace(runner=LocalValidationRunner(5)).race(baseline_dir=d,patches=[bad,good],test_command=[sys.executable,'-m','unittest','discover','-v'])
            self.assertEqual(race['winner']['index'],1)

    def test_24_candidate_race_none(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'x.py','VALUE=0\n');write(r/'test_x.py','import unittest\nimport x\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(x.VALUE,9)\n')
            p=PatchSet('bad',(FilePatch('x.py','VALUE=1\n'),));race=CandidateRace(runner=LocalValidationRunner(5)).race(baseline_dir=d,patches=[p],test_command=[sys.executable,'-m','unittest','discover','-v'])
            self.assertIsNone(race['winner'])

    def test_25_factory_nl_generation(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'test_calc.py','import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(add(2,4),6)\n')
            out=V68CodeFactory(workspace_root=w,max_rounds=2).run(task_id='nl',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='function add(a,b) = a+b in calc.py')
            self.assertEqual(out['status'],'candidate_ready');self.assertEqual(out['manifest']['task_plan']['source'],'natural_language')

    def test_26_factory_nameerror_race(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'helper.py','def norm(x): return x.strip().lower()\n');write(r/'main.py','def run(x): return norm(x)\n');write(r/'test_main.py','import unittest\nfrom main import run\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(run(" A "),"a")\n')
            before=digest_tree(d);out=V68CodeFactory(workspace_root=w,max_rounds=3).run(task_id='r',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair repository')
            self.assertEqual(out['status'],'candidate_ready');self.assertTrue(out['manifest']['races']);self.assertEqual(before,digest_tree(d))

    def test_27_factory_attributeerror(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'impl.py','def ping(): return 7\n');write(r/'api.py','X=1\n');write(r/'test_api.py','import unittest\nimport api\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(api.ping(),7)\n')
            out=V68CodeFactory(workspace_root=w,max_rounds=3).run(task_id='a',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair repository')
            self.assertEqual(out['status'],'candidate_ready')

    def test_28_factory_importerror(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'impl.py','def ping(): return 7\n');write(r/'api.py','X=1\n');write(r/'test_api.py','import unittest\nfrom api import ping\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(ping(),7)\n')
            out=V68CodeFactory(workspace_root=w,max_rounds=3).run(task_id='i',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair repository')
            self.assertEqual(out['status'],'candidate_ready')

    def test_29_factory_keyword_typeerror_with_contract(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'m.py','def scale(value):\n    return value*2\n');write(r/'test_m.py','import unittest\nfrom m import scale\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(scale(amount=3),6)\n')
            structured={'mode':'repair','keyword_aliases':{'amount':'value'}}
            out=V68CodeFactory(workspace_root=w,max_rounds=3).run(task_id='k',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='support amount keyword',structured=structured)
            self.assertEqual(out['status'],'candidate_ready');self.assertTrue(out['manifest']['races'])

    def test_30_factory_keyword_without_contract_rejected(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'m.py','def scale(value):\n    return value*2\n');write(r/'test_m.py','import unittest\nfrom m import scale\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(scale(amount=3),6)\n')
            out=V68CodeFactory(workspace_root=w,max_rounds=2).run(task_id='k2',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair repository')
            self.assertEqual(out['status'],'candidate_rejected')

    def test_31_coordinator_publishes_ready(self):
        class F:
            def run(self,**kw): return {'status':'candidate_ready','manifest':{'schema':2}}
        outbox=Outbox();c=V68CodeFactoryCoordinator(code_factory=F(),outbox=outbox);req={'request_sha256':'a'*64,'request':{'metadata':{'executable':False},'capability_id':'code'}}
        o=c.generate(req,source_repo='x',test_command=['python','-m','unittest'],objective='x');self.assertEqual(o['status'],'candidate_published');self.assertEqual(len(outbox.rows),1)

    def test_32_coordinator_rejects_executable_request(self):
        c=V68CodeFactoryCoordinator(code_factory=object(),outbox=Outbox())
        with self.assertRaises(ValueError): c.generate({'metadata':{'executable':True}},source_repo='x',test_command=[],objective='x')

    def test_33_syntax_expected_colon_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'bad.py','def f()\n    return 1\n');c=RepositoryContextBuilder().build(d)
            failure=f'  File "{r/"bad.py"}", line 1\n    def f()\n           ^\nSyntaxError: expected \':\''
            ps=DiagnosticRepairPlanner().candidates(workspace=d,context=c,failure_text=failure);self.assertEqual(len(ps),1);self.assertEqual(ps[0].reason,'syntax_expected_colon')

    def test_34_factory_syntax_colon_repair(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'bad.py','def f()\n    return 9\n');write(r/'test_bad.py','import unittest\nfrom bad import f\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(f(),9)\n')
            out=V68CodeFactory(workspace_root=w,max_rounds=3).run(task_id='s',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair syntax')
            self.assertEqual(out['status'],'candidate_ready')


if __name__=='__main__': unittest.main()
