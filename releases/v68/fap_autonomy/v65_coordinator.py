from __future__ import annotations
import copy
from typing import Any,Callable,Dict,Optional
from .telemetry import normalize_runtime_telemetry
class V65Coordinator:
    def __init__(self,*,dispatcher,controller,activation_manager,feedback,quarantine,android_sync=None,active_state_loader:Optional[Callable[[],Dict[str,Any]]]=None):self.dispatcher=dispatcher;self.controller=controller;self.activation=activation_manager;self.feedback=feedback;self.quarantine=quarantine;self.android_sync=android_sync;self.active_state_loader=active_state_loader
    def begin(self,*,capability_id,candidate_digest,family=""):
        q=self.quarantine.status(capability_id=capability_id,candidate_digest=candidate_digest,family=family)
        if q["quarantined"]:return {"started":False,"status":"quarantined","quarantine":q}
        st=self.controller.start(capability_id,candidate_digest);self._sync_android(capability_id,candidate_digest,family);return {"started":True,"status":st["status"],"canary":st,"quarantine":q}
    def route(self,*,capability_id,candidate_digest,request_id,baseline=None):
        return self.dispatcher.route(capability_id,request_id=request_id,canary_ratio=self.controller.ratio(capability_id,candidate_digest),baseline=baseline)
    def observe(self,raw):
        event=normalize_runtime_telemetry(raw);inserted=self.controller.ingest(event);decision=self.controller.evaluate(event.capability_id,event.candidate_digest);out=decision.as_dict();out["inserted"]=inserted;out["event_id"]=event.event_id
        if decision.status=="rollback_required":
            rollback=self.activation.rollback(event.capability_id,reason="v65_canary_regression",evidence=copy.deepcopy(out));out["rollback_result"]=rollback
            if rollback.get("rolled_back"):
                out["demotion"]=self.feedback.record(capability_id=event.capability_id,candidate_digest=event.candidate_digest,reason="v65_canary_regression",evidence=copy.deepcopy(out));q=self.quarantine.record_failure(event_id=f"rollback:{event.event_id}",capability_id=event.capability_id,candidate_digest=event.candidate_digest,reason="v65_canary_regression",family=event.family);out["quarantine"]=q;self.controller.mark_rolled_back(event.capability_id,event.candidate_digest,quarantined=bool(q["quarantined"]))
        self._sync_android(event.capability_id,event.candidate_digest,event.family);return out
    def _sync_android(self,capability_id,candidate_digest,family):
        if self.android_sync is None or self.active_state_loader is None:return
        self.android_sync.write(active_state=self.active_state_loader(),canary={capability_id:self.controller.state(capability_id,candidate_digest)},quarantine={capability_id:self.quarantine.status(capability_id=capability_id,candidate_digest=candidate_digest,family=family)})
