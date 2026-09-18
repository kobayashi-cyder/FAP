import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fap_autonomy.code_ir import CodeIRError, FunctionIR
from fap_autonomy.code_lineage import CodeLineageLedger
from fap_autonomy.native_patch_generator import GenerationError, NativePatchGenerator
from fap_autonomy.patch_engine import FilePatch, PatchError, PatchSet, RepositoryPatchApplier
from fap_autonomy.repo_context import RepositoryContextBuilder, RepositoryContextError
from fap_autonomy.repository_code_factory import CodeFactoryError, NativeRepositoryCodeFactory, digest_tree
from fap_autonomy.v67_coordinator import V67CodeFactoryCoordinator


def write(p, s):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding='utf-8')


class Outbox:
    def __init__(self): self.records=[]
    def publish_candidate_manifest(self, **kw): self.records.append(kw); return {'written': True, **kw}


class V67Tests(unittest.TestCase):
    def test_01_context_indexes_symbols(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'a.py','def hello(x):\n    return x\nclass Box:\n    pass\n')
            c=RepositoryContextBuilder().build(d)
            self.assertEqual(c.symbol_index['hello'],('a.py',));self.assertEqual(c.symbol_index['Box'],('a.py',))

    def test_02_context_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'a.py','x=1\n')
            try: os.symlink(r/'a.py',r/'b.py')
            except (OSError,NotImplementedError): self.skipTest('symlink unavailable')
            with self.assertRaises(RepositoryContextError):RepositoryContextBuilder().build(d)

    def test_03_context_budget(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'a.py','x=1\n'*15);write(r/'b.py','y=2\n'*15)
            with self.assertRaises(RepositoryContextError):RepositoryContextBuilder(max_file_bytes=100,max_total_bytes=100).build(d)

    def test_04_ir_generates_real_function(self):
        s=FunctionIR.from_dict({'name':'add','args':['a','b'],'expression':{'add':[{'var':'a'},{'var':'b'}]}}).to_source()
        ns={};exec(s,ns);self.assertEqual(ns['add'](2,3),5);self.assertNotIn('pass',s)

    def test_05_ir_conditional(self):
        s=FunctionIR.from_dict({'name':'clip0','args':['x'],'expression':{'if':{'cond':{'lt':[{'var':'x'},0]},'then':0,'else':{'var':'x'}}}}).to_source()
        ns={};exec(s,ns);self.assertEqual(ns['clip0'](-2),0);self.assertEqual(ns['clip0'](3),3)

    def test_06_ir_rejects_bad_identifier(self):
        with self.assertRaises(CodeIRError):FunctionIR.from_dict({'name':'__x','args':[],'expression':1})

    def test_07_ir_rejects_arbitrary_call(self):
        with self.assertRaises(CodeIRError):FunctionIR.from_dict({'name':'x','args':[],'expression':{'call':{'fn':'eval','args':['1+1']}}}).to_source()

    def test_08_patch_base_hash(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'a.py','x=1\n');a=RepositoryPatchApplier(d)
            with self.assertRaises(PatchError):a.apply(PatchSet('x',(FilePatch('a.py','x=2\n','0'*64),)))

    def test_09_patch_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            a=RepositoryPatchApplier(d)
            with self.assertRaises(PatchError):a.apply(PatchSet('x',(FilePatch('../evil.py','x=1\n'),)))

    def test_10_patch_budget(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PatchError):RepositoryPatchApplier(d,max_patch_bytes=4).apply(PatchSet('x',(FilePatch('a.py','12345'),)))

    def test_11_missing_import_generation(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'helper.py','def normalize(x):\n    return x.strip().lower()\n');write(r/'main.py','def run(x):\n    return normalize(x)\n')
            c=RepositoryContextBuilder().build(d);failure=f'  File "{r/"main.py"}", line 2, in run\nNameError: name \'normalize\' is not defined'
            p=NativePatchGenerator.repair_missing_import(workspace=d,context=c,failure_text=failure)
            self.assertIn('from helper import normalize',p.patches[0].content)

    def test_12_ambiguous_symbol_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'a.py','def f():\n return 1\n');write(r/'b.py','def f():\n return 2\n');write(r/'c.py','def g():\n return f()\n')
            c=RepositoryContextBuilder().build(d);failure=f'File "{r/"c.py"}", line 2\nNameError: name \'f\' is not defined'
            with self.assertRaises(GenerationError):NativePatchGenerator.repair_missing_import(workspace=d,context=c,failure_text=failure)

    def _single_repo(self,r):
        write(r/'helper.py','def normalize(x):\n    return x.strip().lower()\n')
        write(r/'main.py','def run(x):\n    return normalize(x)\n')
        write(r/'test_main.py','import unittest\nfrom main import run\nclass T(unittest.TestCase):\n    def test_x(self): self.assertEqual(run(" A "),"a")\n')

    def test_13_factory_repairs_and_passes(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);self._single_repo(r);before=digest_tree(d)
            f=NativeRepositoryCodeFactory(workspace_root=w,max_rounds=3)
            o=f.run(task_id='t',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair')
            self.assertEqual(o['status'],'candidate_ready');self.assertEqual(digest_tree(d),before)
            self.assertTrue(o['manifest']['lineage_valid']);self.assertEqual(o['manifest']['rounds'],2)

    def test_14_factory_multi_round_two_files(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'helper.py','def a(x): return x+1\ndef b(x): return x*2\n')
            write(r/'one.py','def x(v): return a(v)\n');write(r/'two.py','def y(v): return b(v)\n')
            write(r/'test_all.py','import unittest\nfrom one import x\nfrom two import y\nclass T(unittest.TestCase):\n def test_a(self): self.assertEqual(x(1),2)\n def test_b(self): self.assertEqual(y(2),4)\n')
            f=NativeRepositoryCodeFactory(workspace_root=w,max_rounds=4)
            o=f.run(task_id='t2',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair imports')
            self.assertEqual(o['status'],'candidate_ready');self.assertGreaterEqual(len(o['manifest']['patches']),2)

    def test_15_factory_rejects_unsupported_failure(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'test_bad.py','import unittest\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(1,2)\n')
            o=NativeRepositoryCodeFactory(workspace_root=w,max_rounds=2).run(task_id='bad',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair')
            self.assertEqual(o['status'],'candidate_rejected');self.assertTrue(o['lineage_valid'])

    def test_16_factory_generates_new_function_from_ir(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'test_calc.py','import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(add(2,5),7)\n')
            spec={'target_path':'calc.py','function_spec':{'name':'add','args':['a','b'],'expression':{'add':[{'var':'a'},{'var':'b'}]}}}
            o=NativeRepositoryCodeFactory(workspace_root=w,max_rounds=2).run(task_id='gen',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='generate add',initial_generation=spec)
            self.assertEqual(o['status'],'candidate_ready');self.assertEqual(o['manifest']['rounds'],1)

    def test_17_source_repo_never_mutated_by_generation(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'test_calc.py','import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n def test_x(self): self.assertEqual(add(1,1),2)\n')
            before=digest_tree(d);spec={'target_path':'calc.py','function_spec':{'name':'add','args':['a','b'],'expression':{'add':[{'var':'a'},{'var':'b'}]}}}
            NativeRepositoryCodeFactory(workspace_root=w).run(task_id='x',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='x',initial_generation=spec)
            self.assertEqual(before,digest_tree(d));self.assertFalse((r/'calc.py').exists())

    def test_18_lineage_chain(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'l.jsonl';l=CodeLineageLedger(str(p));l.append('a',{'x':1});l.append('b',{'x':2});self.assertTrue(l.validate())

    def test_19_lineage_tamper_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'l.jsonl';l=CodeLineageLedger(str(p));l.append('a',{'x':1});rows=p.read_text().splitlines();o=json.loads(rows[0]);o['payload']['x']=9;p.write_text(json.dumps(o)+'\n');self.assertFalse(l.validate())

    def test_20_manifest_non_executable(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);self._single_repo(r);o=NativeRepositoryCodeFactory(workspace_root=w).run(task_id='m',source_repo=d,test_command=[sys.executable,'-m','unittest','discover','-v'],objective='repair')
            self.assertFalse(o['manifest']['executable'])

    def test_21_python_c_forbidden(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'a.py','x=1\n')
            with self.assertRaises(CodeFactoryError):NativeRepositoryCodeFactory(workspace_root=w).run(task_id='c',source_repo=d,test_command=[sys.executable,'-c','print(1)'],objective='x')

    def test_22_non_python_command_forbidden(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as w:
            r=Path(d);write(r/'a.py','x=1\n')
            with self.assertRaises(CodeFactoryError):NativeRepositoryCodeFactory(workspace_root=w).run(task_id='c',source_repo=d,test_command=['sh','-c','true'],objective='x')

    def test_23_context_relevant_files(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'math_ops.py','def add(a,b): return a+b\n');write(r/'other.py','def z(): return 0\n');c=RepositoryContextBuilder().build(d)
            self.assertEqual(RepositoryContextBuilder.relevant_files(c,'please fix add')[0],'math_ops.py')

    def test_24_patch_digest_stable(self):
        p=PatchSet('x',(FilePatch('a.py','x=1\n'),));self.assertEqual(p.digest(),p.digest())

    def test_25_coordinator_publishes_only_ready(self):
        class Factory:
            def run(self,**kw):return {'status':'candidate_ready','manifest':{'x':1}}
        out=Outbox();c=V67CodeFactoryCoordinator(code_factory=Factory(),outbox=out)
        req={'request_sha256':'a'*64,'request':{'capability_id':'code','metadata':{'executable':False}}}
        o=c.generate(req,source_repo='x',test_command=['python','-m','unittest'],objective='x')
        self.assertEqual(o['status'],'candidate_published');self.assertEqual(len(out.records),1)

    def test_26_coordinator_rejects_executable_request(self):
        c=V67CodeFactoryCoordinator(code_factory=object(),outbox=Outbox())
        with self.assertRaises(ValueError):c.generate({'metadata':{'executable':True}},source_repo='x',test_command=[],objective='x')

    def test_27_generated_call_whitelist_works(self):
        s=FunctionIR.from_dict({'name':'mag','args':['x'],'expression':{'call':{'fn':'abs','args':[{'var':'x'}]}}}).to_source();ns={};exec(s,ns);self.assertEqual(ns['mag'](-3),3)

    def test_28_candidate_digest_changes_on_patch(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);write(r/'a.py','x=1\n');a=digest_tree(d);write(r/'a.py','x=2\n');self.assertNotEqual(a,digest_tree(d))

if __name__=='__main__':unittest.main()
