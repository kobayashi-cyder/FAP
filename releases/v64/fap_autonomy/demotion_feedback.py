from __future__ import annotations
import json, os, time
from pathlib import Path

class DemotionFeedback:
    def __init__(self,history_path:str,failure_memory_path:str):
        self.history=Path(history_path); self.failure=Path(failure_memory_path); self.history.parent.mkdir(parents=True,exist_ok=True); self.failure.parent.mkdir(parents=True,exist_ok=True)
    def record(self,*,capability_id,candidate_digest,reason,evidence):
        rec={'ts':time.time(),'capability_id':capability_id,'candidate_digest':candidate_digest,'state':'demoted','reason':reason,'evidence':evidence}
        for p,kind in ((self.history,'demotion'),(self.failure,'post_activation_regression')):
            row=dict(rec,kind=kind)
            with p.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
        return rec
