from __future__ import annotations

import hashlib, hmac, json, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from fap_autonomy.attestation import AttestationVerifier
from fap_autonomy.telemetry_v66 import FAPTelemetryEmitter, TelemetryVerifier
from fap_autonomy.statistical_canary import StatisticalStagedCanaryController
from fap_autonomy.quarantine_release import EvidenceQuarantineLedger
from fap_autonomy.repair_bridge import QuarantineRepairEmitter
from fap_autonomy.production_matrix import ProductionCapabilityMatrix
from fap_autonomy.v66_coordinator import V66Coordinator

D1='a'*64; D2='b'*64
ATTEST_SECRET=b'v66-demo-attest-'+b'a'*40
TELEMETRY_SECRET=b'v66-demo-telemetry-'+b't'*40

class Dispatcher:
    def route(self,*a,**k): return {'arm':'synthetic-route',**k}
class Activation:
    def rollback(self,*a,**k): return {'rolled_back':True,'reason':k.get('reason')}
class Feedback:
    def record(self,**k): return {'state':'demoted','reason':k.get('reason')}

def canonical(o): return json.dumps(o,sort_keys=True,separators=(',',':')).encode()

def main():
  with tempfile.TemporaryDirectory() as d:
    r=Path(d); verifier=AttestationVerifier(ATTEST_SECRET,allowed_wrapper_ids={'demo-wrapper'})
    emitter=FAPTelemetryEmitter(str(r/'telemetry.jsonl'),TELEMETRY_SECRET)
    tv=TelemetryVerifier(TELEMETRY_SECRET)
    ctrl=StatisticalStagedCanaryController(str(r/'canary.db'),min_per_arm=80)
    q=EvidenceQuarantineLedger(str(r/'quarantine.db'),candidate_threshold=1,family_threshold=3)
    repair=QuarantineRepairEmitter(str(r/'skill_factory_inbox'))
    matrix=ProductionCapabilityMatrix(str(r/'matrix.db'))
    co=V66Coordinator(dispatcher=Dispatcher(),controller=ctrl,activation_manager=Activation(),feedback=Feedback(),
                      quarantine=q,repair_emitter=repair,production_matrix=matrix,telemetry_verifier=tv)

    counter=0
    def attested(digest):
      nonlocal counter; counter+=1; now=int(time.time()*1000); result={'execution':counter}
      p={'wrapper_id':'demo-wrapper','nonce':f'n{counter}','slot_digest':digest,
         'result_sha256':hashlib.sha256(canonical(result)).hexdigest(),'issued_at_ms':now}
      p['mac']=hmac.new(ATTEST_SECRET,canonical(p),hashlib.sha256).hexdigest()
      return verifier.verify(attestation=p,expected_nonce=p['nonce'],expected_slot_digest=digest,result=result,now_ms=now)
    def emit(digest,arm,success,quality,latency,ratio,tag,family='math-family'):
      row=emitter.emit(request_id=tag,capability_id='math',candidate_digest=digest,arm=arm,success=success,
                       quality=quality,latency_ms=latency,family=family,stage_ratio=ratio,attestation=attested(digest))
      return co.observe(row)

    co.begin(capability_id='math',candidate_digest=D1,family='math-family')
    good_stages=[]
    for stage in (.05,.20,.50):
      last=None
      for i in range(80): last=emit(D1,'baseline',True,.95,10,stage,f'g-{stage}-b-{i}')
      for i in range(80): last=emit(D1,'active',True,.95,10,stage,f'g-{stage}-a-{i}')
      good_stages.append({'stage':stage,'status':last['status'],'next_ratio':last.get('next_ratio')})

    co.begin(capability_id='math',candidate_digest=D2,family='bad-family')
    bad=None
    for i in range(80): bad=emit(D2,'baseline',True,.95,10,.05,f'bad-b-{i}',family='bad-family')
    for i in range(80): bad=emit(D2,'active',False,.35,30,.05,f'bad-a-{i}',family='bad-family')

    release_error=''
    try:
      co.release_quarantine(capability_id='math',candidate_digest=D2,evidence_sha256='1'*64,
                            holdout_score=.4,baseline_score=.9,verified=True,untouched_holdout=True,family='bad-family')
    except ValueError as e: release_error=str(e)
    release=co.release_quarantine(capability_id='math',candidate_digest=D2,
        evidence_sha256=hashlib.sha256(b'fresh-untouched-holdout-v66').hexdigest(),holdout_score=.95,
        baseline_score=.90,verified=True,untouched_holdout=True,family='bad-family')

    out={
      'mechanism_validation_only':True,
      'attestation_kind':'HMAC-SHA256 symmetric host-wrapper attestation',
      'telemetry_authenticated':True,
      'good_candidate_stages':good_stages,
      'good_final_state':ctrl.state('math',D1),
      'bad_candidate_status':bad.get('status'),
      'bad_quarantined':bool(bad.get('quarantine',{}).get('quarantined')),
      'repair_request_queued':bool(bad.get('repair_request',{}).get('queued')),
      'bad_holdout_release_blocked':bool(release_error),
      'fresh_holdout_release':bool(release.get('released')),
      'released_canary_state':ctrl.state('math',D2),
      'matrix':matrix.snapshot('math'),
      'telemetry_lines':len((r/'telemetry.jsonl').read_text().splitlines()),
    }
    target=ROOT/'demo_v66_operational.json'; target.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8')
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=='__main__': main()
