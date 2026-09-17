import json, tempfile
from pathlib import Path

from fap_autonomy.activation import AtomicActivationManager
from fap_autonomy.post_activation_monitor import PostActivationMonitor
from fap_autonomy.promotion_ledger import digest_tree

root=Path(tempfile.mkdtemp(prefix='fap_v63_demo_'))
old=root/'old'; new=root/'new'; old.mkdir(); new.mkdir()
(old/'skill.py').write_text('VALUE=1\n',encoding='utf-8')
(new/'skill.py').write_text('VALUE=2\n',encoding='utf-8')
act=AtomicActivationManager(str(root/'active.json'),str(root/'history'))

def entry(p):
    d=digest_tree(str(p)); return {'candidate_digest':d,'evidence':{'candidate_digest':d,'lifecycle':{'state':'consolidated'}}}

old_rec=act.activate(capability_id='demo',artifact={'candidate_dir':str(old)},registry_entry=entry(old),source_release='v62')
new_rec=act.activate(capability_id='demo',artifact={'candidate_dir':str(new)},registry_entry=entry(new),source_release='v63')
monitor=PostActivationMonitor(str(root/'monitor.db'),min_cases=6,max_success_drop=.10,max_latency_ratio=1.5)
for i,(success,latency) in enumerate([(1,20),(0,22),(0,21),(0,25),(1,24),(0,23)]):
    monitor.ingest(event_id=f'e{i}',candidate_digest=new_rec['candidate_digest'],verified=True,success=bool(success),latency_ms=latency)
decision=monitor.evaluate(candidate_digest=new_rec['candidate_digest'],baseline_success_rate=.90,baseline_latency_ms=10)
rolled=None
if decision.rollback:
    rolled=act.rollback(reason=','.join(decision.reasons))
out={'old_digest':old_rec['candidate_digest'],'new_digest':new_rec['candidate_digest'],'decision':decision.__dict__,'rolled_back_to':rolled['candidate_digest'] if rolled else None,'rollback_matches_old':bool(rolled and rolled['candidate_digest']==old_rec['candidate_digest'])}
print(json.dumps(out,ensure_ascii=False,indent=2))
