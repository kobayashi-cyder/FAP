import pathlib,sys,unittest,subprocess,json
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from deterministic_replay import *
E=[{'id':'1','kind':'observe','value':2},{'id':'2','kind':'decide','value':3}]; C={'mode':'strict','seed':7}
class T(unittest.TestCase):
 def test_roundtrip(self):
  x=canonicalize_replay(E,C); self.assertTrue(verify_replay(x,E,C).ok); self.assertEqual(x.digest,canonicalize_replay(E,C).digest)
 def test_mutation_reorder_omit_duplicate(self):
  x=canonicalize_replay(E,C)
  for bad in ([{'id':'1','kind':'observe','value':9},E[1]],list(reversed(E)),E[:1]): self.assertFalse(verify_replay(x,bad,C).ok)
  with self.assertRaises(ValueError): canonicalize_replay(E+[E[0]],C)
 def test_schema_config_digest(self):
  with self.assertRaises(ValueError): canonicalize_replay(E,C,schema=2)
  with self.assertRaises(ValueError): canonicalize_replay(E,{})
  x=canonicalize_replay(E,C); self.assertFalse(verify_replay(x,E,{'mode':'strict','seed':8}).ok)
  y=ReplayEnvelope(1,C,tuple(E),'x'); self.assertFalse(verify_replay(y,E,C).ok)
 def test_privacy_nondeterminism(self):
  for k in ('timestamp','token','audio_payload','absolute_path','device_id'):
   with self.assertRaises(ValueError): canonicalize_replay([{'id':'1',k:'x'}],C)
  with self.assertRaises(ValueError): canonicalize_replay([{'id':'1','value':1.2}],C)
 def test_runner_success_failure(self):
  def r(s,e,c): return (s or 0)+e['value']
  a=run_replay(E,r,C,initial=0); b=run_replay(E,r,C,initial=0); self.assertTrue(a.ok); self.assertEqual(a.result_digest,b.result_digest)
  def boom(s,e,c): raise RuntimeError('boom')
  self.assertFalse(run_replay(E,boom,C).ok)
 def test_fresh_process_repeatability(self):
  code="import sys;sys.path.insert(0,'releases/v70');from deterministic_replay import *;print(canonicalize_replay(%r,%r).digest)"%(E,C)
  a=subprocess.check_output([sys.executable,'-c',code],text=True).strip(); b=subprocess.check_output([sys.executable,'-c',code],text=True).strip(); self.assertEqual(a,b)
if __name__=='__main__': unittest.main()
