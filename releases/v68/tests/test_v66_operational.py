import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fap_autonomy.attestation import AttestationError, AttestationVerifier, AttestedSandboxRunner, VerifiedAttestation, digest_tree
from fap_autonomy.telemetry_v66 import FAPTelemetryEmitter, TelemetryVerifier, normalize_attested_telemetry
from fap_autonomy.statistical_canary import StatisticalStagedCanaryController
from fap_autonomy.quarantine_release import EvidenceQuarantineLedger
from fap_autonomy.repair_bridge import QuarantineRepairEmitter
from fap_autonomy.production_matrix import ProductionCapabilityMatrix
from fap_autonomy.v66_coordinator import V66Coordinator

D = 'a' * 64
SECRET = b'v66-demo-attestation-key-' + b'x' * 32
TELEMETRY_SECRET = b'v66-telemetry-auth-key-' + b'y' * 32


def raw_event(i, arm='active', success=True, quality=.90, latency=10.0, ratio=.05, digest=D, family='fam'):
    return {
        'event_id': f'e{i}', 'request_id': f'r{i}', 'capability_id': 'math',
        'candidate_digest': digest, 'arm': arm, 'verified': True, 'success': success,
        'quality': quality, 'latency_ms': latency, 'family': family,
        'attestation_verified': True, 'attestation_id': hashlib.sha256(f'att{i}'.encode()).hexdigest(),
        'wrapper_id': 'wrapper-1', 'stage_ratio': ratio, 'production': True,
        'emitted_at_ms': int(time.time() * 1000),
    }


def signed_event(*args, **kwargs):
    row = raw_event(*args, **kwargs)
    row['telemetry_mac'] = hmac.new(TELEMETRY_SECRET, json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    return row


class V66OperationalTests(unittest.TestCase):
    def test_01_attestation_verifies(self):
        v = AttestationVerifier(SECRET, allowed_wrapper_ids={'w'})
        result = {'ok': True}
        now = int(time.time() * 1000)
        payload = {'wrapper_id': 'w', 'nonce': 'n', 'slot_digest': D,
                   'result_sha256': hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                   'issued_at_ms': now}
        mac = hmac.new(SECRET, json.dumps(payload, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
        out = v.verify(attestation={**payload, 'mac': mac}, expected_nonce='n', expected_slot_digest=D, result=result, now_ms=now)
        self.assertEqual(out.wrapper_id, 'w')
        self.assertEqual(len(out.attestation_id), 64)

    def test_02_bad_attestation_mac_rejected(self):
        v = AttestationVerifier(SECRET)
        result = {'ok': True}; now = int(time.time() * 1000)
        payload = {'wrapper_id': 'w', 'nonce': 'n', 'slot_digest': D,
                   'result_sha256': hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                   'issued_at_ms': now, 'mac': '0' * 64}
        with self.assertRaises(AttestationError):
            v.verify(attestation=payload, expected_nonce='n', expected_slot_digest=D, result=result, now_ms=now)

    def test_03_nonce_replay_rejected(self):
        v = AttestationVerifier(SECRET)
        result = {'ok': True}; now = int(time.time() * 1000)
        payload = {'wrapper_id': 'w', 'nonce': 'old', 'slot_digest': D,
                   'result_sha256': hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                   'issued_at_ms': now}
        payload['mac'] = hmac.new(SECRET, json.dumps(payload, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
        with self.assertRaises(AttestationError):
            v.verify(attestation=payload, expected_nonce='new', expected_slot_digest=D, result=result, now_ms=now)

    def test_04_expired_attestation_rejected(self):
        v = AttestationVerifier(SECRET, max_age_ms=10)
        result = {}; issued = 1000
        p = {'wrapper_id': 'w', 'nonce': 'n', 'slot_digest': D,
             'result_sha256': hashlib.sha256(b'{}').hexdigest(), 'issued_at_ms': issued}
        p['mac'] = hmac.new(SECRET, json.dumps(p, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
        with self.assertRaises(AttestationError):
            v.verify(attestation=p, expected_nonce='n', expected_slot_digest=D, result=result, now_ms=2000)

    def test_05_attested_runner_fixed_wrapper(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); slot = r/'slot'; slot.mkdir(); (slot/'skill.py').write_text('x=1\n')
            wrapper = r/'wrapper.py'
            wrapper.write_text('''import hashlib,hmac,json,os,sys,time\nsecret=bytes.fromhex(os.environ["KEYHEX"])\ne=json.load(sys.stdin)\nresult={"ok":True,"echo":e["request"].get("x")}\np={"wrapper_id":"wrapper-1","nonce":e["nonce"],"slot_digest":e["slot_digest"],"result_sha256":hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",", ":")).encode()).hexdigest(),"issued_at_ms":int(time.time()*1000)}\np["mac"]=hmac.new(secret,json.dumps(p,sort_keys=True,separators=(",", ":")).encode(),hashlib.sha256).hexdigest()\njson.dump({"result":result,"attestation":p},sys.stdout)\n''')
            v = AttestationVerifier(SECRET, allowed_wrapper_ids={'wrapper-1'})
            runner = AttestedSandboxRunner([sys.executable, str(wrapper)], v, env={'KEYHEX': SECRET.hex()})
            out = runner.execute(slot=str(slot.resolve()), request={'x': 7})
            self.assertTrue(out['attestation_verified']); self.assertEqual(out['result']['echo'], 7)

    def test_06_attested_runner_inline_code_forbidden(self):
        v = AttestationVerifier(SECRET)
        with self.assertRaises(ValueError):
            AttestedSandboxRunner([sys.executable, '-c', 'print(1)'], v)

    def test_07_digest_tree_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); slot=r/'slot'; slot.mkdir(); target=r/'x'; target.write_text('x')
            try: (slot/'link').symlink_to(target)
            except (OSError, NotImplementedError): self.skipTest('symlink unavailable')
            with self.assertRaises(AttestationError): digest_tree(str(slot.resolve()))

    def test_08_telemetry_emitter_requires_attestation(self):
        with tempfile.TemporaryDirectory() as d:
            em = FAPTelemetryEmitter(str(Path(d)/'t.jsonl'), TELEMETRY_SECRET)
            with self.assertRaises(ValueError):
                em.emit(request_id='r', capability_id='math', candidate_digest=D, arm='active',
                        success=True, quality=.9, latency_ms=1, stage_ratio=.05, attestation={})

    def test_09_telemetry_emitter_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'t.jsonl'; em=FAPTelemetryEmitter(str(p), TELEMETRY_SECRET)
            att=VerifiedAttestation('b'*64,'wrapper-1','n',D,'c'*64,int(time.time()*1000))
            row=em.emit(request_id='r', capability_id='math', candidate_digest=D, arm='active',
                        success=True, quality=.9, latency_ms=1, stage_ratio=.05, attestation=att)
            self.assertTrue(TelemetryVerifier(TELEMETRY_SECRET).verify(row).production)
            self.assertEqual(len(p.read_text().splitlines()),1)

    def _ctrl(self, root, min_per_arm=80):
        c=StatisticalStagedCanaryController(str(Path(root)/'c.db'), min_per_arm=min_per_arm,
                                            max_success_drop=.08,max_quality_drop=.08,max_latency_ratio=1.5)
        c.start('math',D); return c

    def test_10_statistical_healthy_advances(self):
        with tempfile.TemporaryDirectory() as d:
            c=self._ctrl(d)
            for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'b{i}',arm='baseline')))
            for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'a{i}',arm='active')))
            o=c.evaluate('math',D); self.assertEqual(o.status,'advance'); self.assertEqual(o.next_ratio,.2)

    def test_11_new_stage_does_not_reuse_old_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            c=self._ctrl(d)
            for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'b{i}',arm='baseline')))
            for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'a{i}',arm='active')))
            self.assertEqual(c.evaluate('math',D).status,'advance')
            self.assertEqual(c.evaluate('math',D).status,'monitoring')
            self.assertEqual(c.evaluate('math',D).baseline_n,0)

    def test_12_statistical_regression_rolls_back(self):
        with tempfile.TemporaryDirectory() as d:
            c=self._ctrl(d,min_per_arm=30)
            for i in range(30): c.ingest(normalize_attested_telemetry(raw_event(f'b{i}',arm='baseline',success=True,quality=.95,latency=10)))
            for i in range(30): c.ingest(normalize_attested_telemetry(raw_event(f'a{i}',arm='active',success=False,quality=.4,latency=30)))
            self.assertEqual(c.evaluate('math',D).status,'rollback_required')

    def test_13_inconclusive_stays_monitoring(self):
        with tempfile.TemporaryDirectory() as d:
            c=self._ctrl(d,min_per_arm=20)
            for i in range(20): c.ingest(normalize_attested_telemetry(raw_event(f'b{i}',arm='baseline')))
            for i in range(20): c.ingest(normalize_attested_telemetry(raw_event(f'a{i}',arm='active')))
            self.assertEqual(c.evaluate('math',D).status,'monitoring')

    def test_14_quarantine_release_requires_new_untouched_holdout(self):
        with tempfile.TemporaryDirectory() as d:
            q=EvidenceQuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=2)
            q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r')
            q.record_failure(event_id='2',capability_id='math',candidate_digest=D,reason='r')
            with self.assertRaises(ValueError):
                q.release_with_holdout(capability_id='math',candidate_digest=D,evidence_sha256='1'*64,
                                       holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=False)
            o=q.release_with_holdout(capability_id='math',candidate_digest=D,evidence_sha256='1'*64,
                                     holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=True)
            self.assertTrue(o['released']); self.assertFalse(q.is_quarantined(capability_id='math',candidate_digest=D))

    def test_15_holdout_evidence_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as d:
            q=EvidenceQuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=1)
            q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r')
            q.release_with_holdout(capability_id='math',candidate_digest=D,evidence_sha256='2'*64,
                                   holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=True)
            q.record_failure(event_id='2',capability_id='math',candidate_digest=D,reason='r')
            with self.assertRaises(ValueError):
                q.release_with_holdout(capability_id='math',candidate_digest=D,evidence_sha256='2'*64,
                                       holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=True)

    def test_16_bad_holdout_cannot_release(self):
        with tempfile.TemporaryDirectory() as d:
            q=EvidenceQuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=1)
            q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r')
            with self.assertRaises(ValueError):
                q.release_with_holdout(capability_id='math',candidate_digest=D,evidence_sha256='3'*64,
                                       holdout_score=.5,baseline_score=.9,verified=True,untouched_holdout=True)

    def test_17_repair_emitter_is_non_executable_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            e=QuarantineRepairEmitter(d); a=e.emit(capability_id='math',candidate_digest=D,reason='regression')
            b=e.emit(capability_id='math',candidate_digest=D,reason='regression')
            self.assertTrue(a['queued']); self.assertTrue(b['duplicate'])
            self.assertFalse(a['spec']['metadata']['executable'])
            self.assertTrue(a['spec']['requirements']['new_untouched_holdout_evidence_required_for_release'])

    def test_18_production_matrix_accepts_attested_only(self):
        with tempfile.TemporaryDirectory() as d:
            m=ProductionCapabilityMatrix(str(Path(d)/'m.db'))
            ev=normalize_attested_telemetry(raw_event('1'))
            self.assertTrue(m.ingest(ev)); self.assertFalse(m.ingest(ev))
            s=m.snapshot('math'); self.assertEqual(s['n'],1); self.assertFalse(s['public_benchmark'])

    def test_19_coordinator_quarantine_emits_repair_and_matrix(self):
        class Disp:
            def route(self,*a,**k): return k
        class Act:
            def rollback(self,*a,**k): return {'rolled_back':True}
        class Feed:
            def record(self,**k): return {'state':'demoted'}
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); c=StatisticalStagedCanaryController(str(r/'c.db'),min_per_arm=30)
            q=EvidenceQuarantineLedger(str(r/'q.db'),candidate_threshold=1); rep=QuarantineRepairEmitter(str(r/'in'))
            m=ProductionCapabilityMatrix(str(r/'m.db'))
            co=V66Coordinator(dispatcher=Disp(),controller=c,activation_manager=Act(),feedback=Feed(),quarantine=q,
                              repair_emitter=rep,production_matrix=m,telemetry_verifier=TelemetryVerifier(TELEMETRY_SECRET))
            co.begin(capability_id='math',candidate_digest=D,family='fam')
            out=None
            for i in range(30): out=co.observe(signed_event(f'b{i}',arm='baseline',success=True,quality=.95,latency=10))
            for i in range(30): out=co.observe(signed_event(f'a{i}',arm='active',success=False,quality=.4,latency=30))
            self.assertIn('repair_request',out); self.assertTrue(out['quarantine']['quarantined'])
            snap=m.snapshot('math'); self.assertEqual(snap['n'],60); self.assertEqual(snap['control_events']['rollback'],1)

    def test_20_release_resets_canary_and_requires_fresh_evidence(self):
        class X:
            def route(self,*a,**k): return k
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); c=StatisticalStagedCanaryController(str(r/'c.db'),min_per_arm=2); c.start('math',D); c.mark_rolled_back('math',D,quarantined=True)
            q=EvidenceQuarantineLedger(str(r/'q.db'),candidate_threshold=1); q.record_failure(event_id='1',capability_id='math',candidate_digest=D,reason='r')
            m=ProductionCapabilityMatrix(str(r/'m.db')); co=V66Coordinator(dispatcher=X(),controller=c,activation_manager=X(),feedback=X(),quarantine=q,
                repair_emitter=QuarantineRepairEmitter(str(r/'in')),production_matrix=m,telemetry_verifier=TelemetryVerifier(TELEMETRY_SECRET))
            o=co.release_quarantine(capability_id='math',candidate_digest=D,evidence_sha256='4'*64,
                                    holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=True)
            self.assertTrue(o['released']); self.assertEqual(o['canary_reset']['ratio'],.05); self.assertEqual(o['canary_reset']['status'],'running')

    def test_21_duplicate_attestation_cannot_bias_matrix_or_canary(self):
        class Disp:
            def route(self,*a,**k): return k
        class X: pass
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); c=StatisticalStagedCanaryController(str(r/'c.db'),min_per_arm=2)
            q=EvidenceQuarantineLedger(str(r/'q.db')); m=ProductionCapabilityMatrix(str(r/'m.db'))
            co=V66Coordinator(dispatcher=Disp(),controller=c,activation_manager=X(),feedback=X(),quarantine=q,repair_emitter=QuarantineRepairEmitter(str(r/'in')),production_matrix=m,telemetry_verifier=TelemetryVerifier(TELEMETRY_SECRET))
            co.begin(capability_id='math',candidate_digest=D)
            a=signed_event('one',arm='baseline'); b=raw_event('two',arm='baseline'); b['attestation_id']=a['attestation_id']; b['telemetry_mac']=hmac.new(TELEMETRY_SECRET,json.dumps(b,ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode(),hashlib.sha256).hexdigest()
            self.assertTrue(co.observe(a)['matrix_inserted'])
            o=co.observe(b); self.assertEqual(o['status'],'duplicate_evidence')
            self.assertEqual(m.snapshot('math')['n'],1)

    def test_22_stale_stage_telemetry_not_counted_in_new_stage(self):
        with tempfile.TemporaryDirectory() as d:
            c=self._ctrl(d)
            for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'b{i}',arm='baseline',ratio=.05)))
            for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'a{i}',arm='active',ratio=.05)))
            self.assertEqual(c.evaluate('math',D).next_ratio,.2)
            stale=normalize_attested_telemetry(raw_event('stale',arm='active',ratio=.05))
            self.assertFalse(c.ingest(stale))
            self.assertEqual(c.evaluate('math',D).active_n,0)

    def test_23_forged_telemetry_mac_rejected(self):
        v=TelemetryVerifier(TELEMETRY_SECRET); row=raw_event('forge'); row['telemetry_mac']='0'*64
        with self.assertRaises(ValueError): v.verify(row)

    def test_24_emitter_requires_verified_attestation_object(self):
        with tempfile.TemporaryDirectory() as d:
            em=FAPTelemetryEmitter(str(Path(d)/'t.jsonl'),TELEMETRY_SECRET)
            with self.assertRaises(ValueError):
                em.emit(request_id='r',capability_id='math',candidate_digest=D,arm='active',success=True,quality=.9,latency_ms=1,stage_ratio=.05,attestation={'attestation_id':'b'*64})

    def test_25_statistical_full_5_20_50_100(self):
        with tempfile.TemporaryDirectory() as d:
            c=self._ctrl(d)
            for stage,next_expected in ((.05,.2),(.2,.5),(.5,1.0)):
                for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'{stage}-b-{i}',arm='baseline',ratio=stage)))
                for i in range(80): c.ingest(normalize_attested_telemetry(raw_event(f'{stage}-a-{i}',arm='active',ratio=stage)))
                o=c.evaluate('math',D); self.assertEqual(o.next_ratio,next_expected)
            self.assertEqual(c.state('math',D)['status'],'complete'); self.assertEqual(c.ratio('math',D),1.0)

    def test_26_family_quarantine_requires_family_holdout_release(self):
        with tempfile.TemporaryDirectory() as d:
            q=EvidenceQuarantineLedger(str(Path(d)/'q.db'),candidate_threshold=9,family_threshold=2)
            q.record_failure(event_id='1',capability_id='math',candidate_digest='a'*64,reason='r',family='fam')
            q.record_failure(event_id='2',capability_id='math',candidate_digest='b'*64,reason='r',family='fam')
            self.assertTrue(q.status(capability_id='math',candidate_digest='a'*64,family='fam')['quarantined'])
            with self.assertRaises(ValueError):
                q.release_with_holdout(capability_id='math',candidate_digest='a'*64,evidence_sha256='5'*64,holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=True,family='fam',scope='candidate')
            o=q.release_with_holdout(capability_id='math',candidate_digest='a'*64,evidence_sha256='6'*64,holdout_score=.9,baseline_score=.9,verified=True,untouched_holdout=True,family='fam',scope='family')
            self.assertTrue(o['released'])

    def test_27_attestation_result_tamper_rejected(self):
        v=AttestationVerifier(SECRET); now=int(time.time()*1000); result={'x':1}
        p={'wrapper_id':'w','nonce':'n','slot_digest':D,'result_sha256':hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',', ':')).encode()).hexdigest(),'issued_at_ms':now}
        p['mac']=hmac.new(SECRET,json.dumps(p,sort_keys=True,separators=(',', ':')).encode(),hashlib.sha256).hexdigest()
        with self.assertRaises(AttestationError): v.verify(attestation=p,expected_nonce='n',expected_slot_digest=D,result={'x':2},now_ms=now)

    def test_28_telemetry_field_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            att=VerifiedAttestation('b'*64,'wrapper-1','n',D,'c'*64,int(time.time()*1000))
            row=FAPTelemetryEmitter(str(Path(d)/'t.jsonl'),TELEMETRY_SECRET).emit(request_id='r',capability_id='math',candidate_digest=D,arm='active',success=True,quality=.9,latency_ms=1,stage_ratio=.05,attestation=att)
            row['success']=False
            with self.assertRaises(ValueError): TelemetryVerifier(TELEMETRY_SECRET).verify(row)


if __name__ == '__main__': unittest.main()
