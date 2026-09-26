import json,tempfile,unittest
from pathlib import Path
from fap_autonomy.runtime_dispatcher import ActiveRuntimeDispatcher,RuntimeDispatchError,SandboxedRuntimeBridge,digest_tree
from fap_autonomy.ab_observer import ABObserver
from fap_autonomy.android_state_sync import AndroidStateSync
from fap_autonomy.demotion_feedback import DemotionFeedback

class V64Tests(unittest.TestCase):
 def test_dispatch_digest_and_canary(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td); s=r/'slot';s.mkdir();(s/'x.py').write_text('x=1');d=digest_tree(str(s));(r/'active.json').write_text(json.dumps({'active':{'math':{'candidate_digest':d,'slot':str(s)}}})); q=ActiveRuntimeDispatcher(str(r/'active.json'));self.assertEqual(q.resolve('math')['candidate_digest'],d);self.assertEqual(q.route('math',request_id='a',canary_ratio=0)['arm'],'baseline');self.assertEqual(q.route('math',request_id='a',canary_ratio=1)['arm'],'active')
 def test_dispatch_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);s=r/'slot';s.mkdir();(s/'x').write_text('a');d=digest_tree(str(s));(r/'a.json').write_text(json.dumps({'active':{'c':{'candidate_digest':d,'slot':str(s)}}}));(s/'x').write_text('b')
   with self.assertRaises(RuntimeDispatchError):ActiveRuntimeDispatcher(str(r/'a.json')).resolve('c')
 def test_canary_deterministic(self): self.assertEqual(ActiveRuntimeDispatcher.canary_bucket('id'),ActiveRuntimeDispatcher.canary_bucket('id'))
 def test_bad_ratio(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):ActiveRuntimeDispatcher(str(Path(td)/'a')).route('c',request_id='x',canary_ratio=1.1)
 def test_ab_small_sample(self):
  with tempfile.TemporaryDirectory() as td:
   o=ABObserver(str(Path(td)/'a.db'),min_per_arm=2);o.ingest(event_id='1',capability_id='c',candidate_digest='d',arm='active',verified=True,success=True,quality=.9,latency_ms=10);self.assertEqual(o.decide(capability_id='c',candidate_digest='d').status,'monitoring')
 def test_ab_regression(self):
  with tempfile.TemporaryDirectory() as td:
   o=ABObserver(str(Path(td)/'a.db'),min_per_arm=2)
   for i in range(2):o.ingest(event_id='b'+str(i),capability_id='c',candidate_digest='d',arm='baseline',verified=True,success=True,quality=.9,latency_ms=10)
   for i in range(2):o.ingest(event_id='a'+str(i),capability_id='c',candidate_digest='d',arm='active',verified=True,success=False,quality=.5,latency_ms=30)
   self.assertTrue(o.decide(capability_id='c',candidate_digest='d').rollback)
 def test_unverified_ignored(self):
  with tempfile.TemporaryDirectory() as td:self.assertFalse(ABObserver(str(Path(td)/'a.db')).ingest(event_id='e',capability_id='c',candidate_digest='d',arm='active',verified=False,success=False,quality=.1,latency_ms=1))
 def test_duplicate_ignored(self):
  with tempfile.TemporaryDirectory() as td:
   o=ABObserver(str(Path(td)/'a.db')); self.assertTrue(o.ingest(event_id='e',capability_id='c',candidate_digest='d',arm='active',verified=True,success=True,quality=.9,latency_ms=1)); self.assertFalse(o.ingest(event_id='e',capability_id='c',candidate_digest='d',arm='active',verified=True,success=True,quality=.9,latency_ms=1))
 def test_android_sync_strips_slot(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.json';d=AndroidStateSync(str(p)).write({'active':{'c':{'candidate_digest':'x','slot':'SECRET','activated_at':1}}});self.assertNotIn('slot',d['active']['c'])
 def test_demotion_feedback_two_logs(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);DemotionFeedback(str(r/'h'),str(r/'f')).record(capability_id='c',candidate_digest='d',reason='r',evidence={});self.assertTrue((r/'h').read_text());self.assertIn('post_activation_regression',(r/'f').read_text())
 def test_ab_healthy(self):
  with tempfile.TemporaryDirectory() as td:
   o=ABObserver(str(Path(td)/'a.db'),min_per_arm=2)
   for i in range(2):o.ingest(event_id='b'+str(i),capability_id='c',candidate_digest='d',arm='baseline',verified=True,success=True,quality=.8,latency_ms=10)
   for i in range(2):o.ingest(event_id='a'+str(i),capability_id='c',candidate_digest='d',arm='active',verified=True,success=True,quality=.85,latency_ms=11)
   self.assertEqual(o.decide(capability_id='c',candidate_digest='d').status,'healthy')
 def test_quality_out_of_range_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   o=ABObserver(str(Path(td)/'a.db'))
   with self.assertRaises(ValueError):o.ingest(event_id='e',capability_id='c',candidate_digest='d',arm='active',verified=True,success=True,quality=1.5,latency_ms=1)
 def test_dispatch_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);s=r/'slot';s.mkdir();target=r/'target';target.write_text('x');(s/'ln').symlink_to(target);d=digest_tree(str(s));(r/'a.json').write_text(json.dumps({'active':{'c':{'candidate_digest':d,'slot':str(s)}}}))
   with self.assertRaises(RuntimeDispatchError):ActiveRuntimeDispatcher(str(r/'a.json')).resolve('c')
 def test_android_sync_atomic_sanitized(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'out.json';s=AndroidStateSync(str(p));s.write({'active':{'c':{'candidate_digest':'d','slot':'/private','source':'verified_registry','baseline_quality':.8,'baseline_latency_ms':12}}});obj=json.loads(p.read_text());self.assertNotIn('slot',obj['active']['c']);self.assertEqual(obj['active']['c']['source'],'verified_registry')
 def test_sandbox_bridge_calls_runner_only_after_verification(self):
  class Runner:
   def __init__(self): self.calls=[]
   def execute(self,*,slot,request): self.calls.append((slot,request)); return {'ok':True}
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);s=r/'slot';s.mkdir();(s/'x').write_text('a');d=digest_tree(str(s));(r/'a.json').write_text(json.dumps({'active':{'c':{'candidate_digest':d,'slot':str(s)}}})); runner=Runner(); out=SandboxedRuntimeBridge(ActiveRuntimeDispatcher(str(r/'a.json')),runner).execute('c',request_id='x',request={'q':1},canary_ratio=1); self.assertEqual(out['arm'],'active'); self.assertEqual(len(runner.calls),1)
 def test_sandbox_bridge_tamper_never_calls_runner(self):
  class Runner:
   def __init__(self): self.calls=0
   def execute(self,**kw): self.calls+=1
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);s=r/'slot';s.mkdir();(s/'x').write_text('a');d=digest_tree(str(s));(r/'a.json').write_text(json.dumps({'active':{'c':{'candidate_digest':d,'slot':str(s)}}}));(s/'x').write_text('b');runner=Runner(); bridge=SandboxedRuntimeBridge(ActiveRuntimeDispatcher(str(r/'a.json')),runner)
   with self.assertRaises(RuntimeDispatchError): bridge.execute('c',request_id='x',request={},canary_ratio=1)
   self.assertEqual(runner.calls,0)
 def test_sandbox_bridge_baseline_does_not_call_runner(self):
  class Runner:
   def __init__(self): self.calls=0
   def execute(self,**kw): self.calls+=1
  with tempfile.TemporaryDirectory() as td:
   runner=Runner();out=SandboxedRuntimeBridge(ActiveRuntimeDispatcher(str(Path(td)/'missing.json')),runner).execute('c',request_id='x',request={},canary_ratio=1,baseline={'name':'base'});self.assertEqual(out['arm'],'baseline');self.assertEqual(runner.calls,0)
 def test_negative_latency_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   o=ABObserver(str(Path(td)/'a.db'))
   with self.assertRaises(ValueError):o.ingest(event_id='e',capability_id='c',candidate_digest='d',arm='active',verified=True,success=True,quality=.5,latency_ms=-1)
 def test_coordinator_demotion_is_json_serializable(self):
  from fap_autonomy.v64_coordinator import V64Coordinator
  class Activation:
   def rollback(self,*a,**kw): return {'rolled_back':True}
  with tempfile.TemporaryDirectory() as td:
   r=Path(td); o=ABObserver(str(r/'a.db'),min_per_arm=1); f=DemotionFeedback(str(r/'h'),str(r/'fm')); c=V64Coordinator(dispatcher=None,observer=o,activation_manager=Activation(),feedback=f)
   c.observe(event_id='b',capability_id='c',candidate_digest='d',arm='baseline',verified=True,success=True,quality=.9,latency_ms=10)
   out=c.observe(event_id='a',capability_id='c',candidate_digest='d',arm='active',verified=True,success=False,quality=.2,latency_ms=30)
   json.dumps(out); self.assertIn('demotion',out)
