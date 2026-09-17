import json, tempfile
from pathlib import Path
from fap_autonomy.runtime_dispatcher import ActiveRuntimeDispatcher, digest_tree
from fap_autonomy.ab_observer import ABObserver
from fap_autonomy.demotion_feedback import DemotionFeedback
from fap_autonomy.v64_coordinator import V64Coordinator
from fap_autonomy.android_state_sync import AndroidStateSync

class FakeActivation:
    def __init__(self, old_digest): self.old_digest=old_digest; self.calls=0
    def rollback(self, capability_id, *, reason, evidence=None):
        self.calls += 1
        return {'rolled_back': True, 'reason': reason, 'to': {'candidate_digest': self.old_digest}}

with tempfile.TemporaryDirectory(prefix='fap_v64_demo_') as td:
    root=Path(td); slot=root/'slot'; slot.mkdir(); (slot/'skill.py').write_text('VALUE=2\n',encoding='utf-8')
    digest=digest_tree(str(slot)); old='0'*64
    active={'schema':1,'active':{'math':{'candidate_digest':digest,'slot':str(slot),'source':'verified_registry','activated_at':1}}}
    state=root/'active.json'; state.write_text(json.dumps(active),encoding='utf-8')
    dispatcher=ActiveRuntimeDispatcher(str(state)); observer=ABObserver(str(root/'ab.db'),min_per_arm=12)
    feedback=DemotionFeedback(str(root/'demotions.jsonl'),str(root/'failure_memory.jsonl'))
    activation=FakeActivation(old)
    coord=V64Coordinator(dispatcher=dispatcher,observer=observer,activation_manager=activation,feedback=feedback)
    for i in range(12): coord.observe(event_id=f'b{i}',capability_id='math',candidate_digest=digest,arm='baseline',verified=True,success=True,quality=.92,latency_ms=10)
    decision=None
    for i in range(12): decision=coord.observe(event_id=f'a{i}',capability_id='math',candidate_digest=digest,arm='active',verified=True,success=(i<6),quality=.60,latency_ms=24)
    android=AndroidStateSync(str(root/'android_state.json')).write(active)
    out={'decision':decision,'rollback_calls':activation.calls,'failure_memory_written':(root/'failure_memory.jsonl').exists(),'android_contains_slot':'slot' in json.dumps(android)}
    print(json.dumps(out,ensure_ascii=False,indent=2))
