import json,sys,tempfile,unittest
from pathlib import Path
from fap_autonomy.android_v65_sync import AndroidV65StateSync
from fap_autonomy.canary_controller import StagedCanaryController
from fap_autonomy.quarantine import QuarantineLedger
from fap_autonomy.skill_factory_worker import SkillFactoryHandoff
from fap_autonomy.telemetry import RuntimeTelemetry,normalize_runtime_telemetry
from fap_autonomy.trusted_runner import TrustedSandboxRunner
from fap_autonomy.v65_coordinator import V65Coordinator
D='a'*64
def telemetry(i,arm='active',digest=D,success=True,quality=.9,latency=10,family='fam'):return RuntimeTelemetry(str(i),str(i),'math',digest,arm,True,success,quality,latency,family)
class V65OperationalTests(unittest.TestCase):
 def test_01_telemetry_accept(self):self.assertTrue(normalize_runtime_telemetry({'event_id':'e','request_id':'r','capability_id':'math','candidate_digest':D,'arm':'active','verified':True,'success':True,'quality':.9,'latency_ms':1}).verified)
 def test_02_unverified_rejected(self):
  with self.assertRaises(ValueError):normalize_runtime_telemetry({'event_id':'e','request_id':'r','capability_id':'math','candidate_digest':D,'arm':'active','verified':False,'success':True,'quality':.9,'latency_ms':1})
 def test_03_bad_digest_rejected(self):
  with self.assertRaises(ValueError):normalize_runtime_telemetry({'event_id':'e','request_id':'r','capability_id':'math','candidate_digest':'x','arm':'active','verified':True,'success':True,'quality':.9,'latency_ms':1})
 def test_04_quality_rejected(self):
  with self.assertRaises(ValueError):normalize_runtime_telemetry({'event_id':'e','request_id':'r','capability_id':'math','candidate_digest':D,'arm':'active','verified':True,'success':True,'quality':1.1,'latency_ms':1})
 def test_05_negative_latency_rejected(self):
  with self.assertRaises(ValueError):normalize_runtime_telemetry({'event_id':'e','request_id':'r','capability_id':'math','candidate_digest':D,'arm':'active','verified':True,'success':True,'quality':.9,'latency_ms':-1})
 def _c(self,r):c=StagedCanaryController(str(Path(r)/'c.db'),min_per_arm=2);c.start('math',D);return c
 def _h(self,c,p):
  [c.ingest(telemetry(f'{p}b{i}','baseline')) for i in range(2)];[c.ingest(telemetry(f'{p}a{i}','active')) for i in range(2)];return c.evaluate('math',D)
 def test_06_stages_5_20_50_100(self):
  with tempfile.TemporaryDirectory() as d:
   c=self._c(d);self.assertEqual(self._h(c,'1').next_ratio,.2);self.assertEqual(c.evaluate('math',D).active_n,0);self.assertEqual(self._h(c,'2').next_ratio,.5);self.assertEqual(self._h(c,'3').status,'complete');self.assertEqual(c.ratio('math',D),1.0)
 def test_07_regression_detected(self):
  with tempfile.TemporaryDirectory() as d:
   c=self._c(d);[c.ingest(telemetry(f'b{i}','baseline',success=True,quality=.95,latency=10)) for i in range(2)];[c.ingest(telemetry(f'a{i}','active',success=False,quality=.4,latency=30)) for i in range(2)];self.assertEqual(c.evaluate('math',D).status,'rollback_required')
 def test_08_duplicate_telemetry_safe(self):
  with tempfile.TemporaryDirectory() as d:c=self._c(d);x=telemetry('dup','baseline');self.assertTrue(c.ingest(x));self.assertFalse(c.ingest(x))
 def test_09_candidate_quarantine(self):
  with tempfile.TemporaryDirectory() as d:q=QuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=2,family_threshold=9);q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r');self.assertTrue(q.record_failure(event_id='2',capability_id='math',candidate_digest=D,reason='r')['quarantined'])
 def test_10_family_quarantine(self):
  with tempfile.TemporaryDirectory() as d:q=QuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=9,family_threshold=2);q.record_failure(event_id='1',capability_id='math',candidate_digest='b'*64,reason='r',family='fam');self.assertTrue(q.record_failure(event_id='2',capability_id='math',candidate_digest='c'*64,reason='r',family='fam')['quarantined'])
 def test_11_duplicate_failure_safe(self):
  with tempfile.TemporaryDirectory() as d:q=QuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=2);q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r');self.assertEqual(q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r')['candidate_failures'],1)
 def test_12_skill_factory_claim_publish_collect(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);h=SkillFactoryHandoff(r/'in',r/'out',r/'done');(r/'in'/'r.json').write_text(json.dumps({'capability_id':'math','metadata':{'executable':False}}),encoding='utf-8');c=h.claim_next();h.publish_candidate_manifest(request_sha256=c['request_sha256'],manifest={'candidate_dir':'x'});self.assertEqual(h.collect_candidate(request_sha256=c['request_sha256'])['manifest']['candidate_dir'],'x')
 def test_13_executable_request_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);h=SkillFactoryHandoff(r/'in',r/'out',r/'done');(r/'in'/'r.json').write_text(json.dumps({'capability_id':'x','metadata':{'executable':True}}),encoding='utf-8');
   with self.assertRaises(ValueError):h.claim_next()
 def test_14_android_no_slot_leak(self):
  with tempfile.TemporaryDirectory() as d:s=AndroidV65StateSync(str(Path(d)/'s.json'));o=s.write(active_state={'active':{'math':{'candidate_digest':D,'slot':'/secret/path'}}},canary={'math':{'ratio':.2}},quarantine={'math':{'quarantined':False}});self.assertNotIn('slot',json.dumps(o));self.assertNotIn('/secret/path',json.dumps(o))
 def test_15_trusted_runner_protocol(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);slot=r/'slot';slot.mkdir();h=r/'w.py';h.write_text("import json,sys;o=json.load(sys.stdin);json.dump({'ok':True},sys.stdout)");self.assertTrue(TrustedSandboxRunner([sys.executable,str(h)]).execute(slot=str(slot.resolve()),request={})['ok'])
 def test_16_inline_runner_code_rejected(self):
  with self.assertRaises(ValueError):TrustedSandboxRunner([sys.executable,'-c','print(1)'])
 def test_17_coordinator_rollback_quarantine(self):
  class Disp:
   def route(self,*a,**k):return k
  class Act:
   def rollback(self,*a,**k):return {'rolled_back':True}
  class Feed:
   def record(self,**k):return {'state':'demoted'}
  with tempfile.TemporaryDirectory() as d:
   c=StagedCanaryController(str(Path(d)/'c.db'),min_per_arm=2);q=QuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=1);co=V65Coordinator(dispatcher=Disp(),controller=c,activation_manager=Act(),feedback=Feed(),quarantine=q);co.begin(capability_id='math',candidate_digest=D,family='fam');[co.observe({'event_id':f'b{i}','request_id':f'b{i}','capability_id':'math','candidate_digest':D,'arm':'baseline','verified':True,'success':True,'quality':.95,'latency_ms':10,'family':'fam'}) for i in range(2)];co.observe({'event_id':'a0','request_id':'a0','capability_id':'math','candidate_digest':D,'arm':'active','verified':True,'success':False,'quality':.4,'latency_ms':30,'family':'fam'});o=co.observe({'event_id':'a1','request_id':'a1','capability_id':'math','candidate_digest':D,'arm':'active','verified':True,'success':False,'quality':.4,'latency_ms':30,'family':'fam'});self.assertTrue(o['quarantine']['quarantined'])
 def test_18_quarantined_candidate_cannot_begin(self):
  class X:pass
  with tempfile.TemporaryDirectory() as d:c=StagedCanaryController(str(Path(d)/'c.db'));q=QuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=1);q.record_failure(event_id='f',capability_id='math',candidate_digest=D,reason='r');co=V65Coordinator(dispatcher=X(),controller=c,activation_manager=X(),feedback=X(),quarantine=q);self.assertFalse(co.begin(capability_id='math',candidate_digest=D)['started'])
