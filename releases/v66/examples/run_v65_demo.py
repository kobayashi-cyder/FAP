from __future__ import annotations
import json, tempfile, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fap_autonomy.canary_controller import StagedCanaryController
from fap_autonomy.quarantine import QuarantineLedger
from fap_autonomy.v65_coordinator import V65Coordinator
from fap_autonomy.android_v65_sync import AndroidV65StateSync

GOOD='1'*64
BAD='2'*64

class Dispatcher:
    def route(self, capability_id, request_id, canary_ratio, baseline=None):
        return {'arm':'active' if canary_ratio > 0 else 'baseline','ratio':canary_ratio}
class Activation:
    def rollback(self, capability_id, reason, evidence):
        return {'rolled_back':True,'from':BAD,'to':GOOD,'reason':reason}
class Feedback:
    def __init__(self): self.rows=[]
    def record(self, **kw): self.rows.append(kw); return {'state':'demoted','reason':kw['reason']}

def event(prefix, i, digest, arm, success=True, quality=.93, latency=10, family='math'):
    return {'event_id':f'{prefix}{i}','request_id':f'{prefix}{i}','capability_id':'math','candidate_digest':digest,
            'arm':arm,'verified':True,'success':success,'quality':quality,'latency_ms':latency,'family':family}

def feed_healthy(co, digest, prefix):
    out=None
    for i in range(2): out=co.observe(event(prefix+'b',i,digest,'baseline'))
    for i in range(2): out=co.observe(event(prefix+'a',i,digest,'active'))
    return out

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    controller=StagedCanaryController(str(root/'canary.db'),min_per_arm=2)
    quarantine=QuarantineLedger(str(root/'quarantine.db'),candidate_threshold=1,family_threshold=2)
    feedback=Feedback(); android_path=root/'android_state.json'; sync=AndroidV65StateSync(str(android_path))
    co=V65Coordinator(dispatcher=Dispatcher(),controller=controller,activation_manager=Activation(),
                      feedback=feedback,quarantine=quarantine,android_sync=sync,
                      active_state_loader=lambda:{'active':{'math':{'candidate_digest':GOOD,'slot':'/private/slot'}}})

    co.begin(capability_id='math',candidate_digest=GOOD,family='math')
    stages=[]
    for n in range(3):
        result=feed_healthy(co,GOOD,f's{n}')
        stages.append({'status':result['status'],'ratio':result['ratio'],'next_ratio':result['next_ratio']})

    co.begin(capability_id='math',candidate_digest=BAD,family='math_bad')
    for i in range(2): co.observe(event('rb',i,BAD,'baseline',True,.96,10,'math_bad'))
    co.observe(event('ra',0,BAD,'active',False,.5,28,'math_bad'))
    bad=co.observe(event('ra',1,BAD,'active',False,.5,28,'math_bad'))

    report={
        'healthy_progression':stages,
        'healthy_final_state':controller.state('math',GOOD),
        'bad_status':bad['status'],
        'rollback':bad.get('rollback_result'),
        'quarantine':bad.get('quarantine'),
        'feedback_rows':len(feedback.rows),
        'android_slot_leaked':'/private/slot' in android_path.read_text(encoding='utf-8'),
        'note':'synthetic mechanism validation only; not a public benchmark score',
    }
    print(json.dumps(report,indent=2,sort_keys=True))
