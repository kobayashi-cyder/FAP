from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Optional

from .telemetry_v66 import TelemetryVerifier


class V66Coordinator:
    def __init__(self, *, dispatcher, controller, activation_manager, feedback, quarantine,
                 repair_emitter, production_matrix, telemetry_verifier: TelemetryVerifier, android_sync=None,
                 active_state_loader: Optional[Callable[[], Dict[str, Any]]] = None):
        self.dispatcher = dispatcher; self.controller = controller; self.activation = activation_manager
        self.feedback = feedback; self.quarantine = quarantine; self.repair = repair_emitter
        self.matrix = production_matrix; self.telemetry_verifier = telemetry_verifier
        self.android_sync = android_sync; self.active_state_loader = active_state_loader

    def begin(self, *, capability_id: str, candidate_digest: str, family: str = "") -> Dict[str, Any]:
        q = self.quarantine.status(capability_id=capability_id, candidate_digest=candidate_digest, family=family)
        if q["quarantined"]:
            return {"started": False, "status": "quarantined", "quarantine": q}
        st = self.controller.start(capability_id, candidate_digest)
        return {"started": True, "status": st["status"], "canary": st, "quarantine": q}

    def route(self, *, capability_id: str, candidate_digest: str, request_id: str,
              baseline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ratio = self.controller.ratio(capability_id, candidate_digest)
        return self.dispatcher.route(capability_id, request_id=request_id, canary_ratio=ratio, baseline=baseline)

    def observe(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        event = self.telemetry_verifier.verify(raw)
        matrix_inserted = self.matrix.ingest(event)
        if not matrix_inserted:
            return {"status": "duplicate_evidence", "inserted": False, "matrix_inserted": False, "event_id": event.event_id}
        inserted = self.controller.ingest(event)
        decision = self.controller.evaluate(event.capability_id, event.candidate_digest)
        out = decision.as_dict(); out.update({"inserted": inserted, "matrix_inserted": matrix_inserted, "event_id": event.event_id})
        if decision.status in {"advance", "complete"}:
            self.matrix.record_control(capability_id=event.capability_id, candidate_digest=event.candidate_digest,
                                       kind=decision.status, payload=copy.deepcopy(out))
        if decision.status == "rollback_required":
            evidence = copy.deepcopy(out)
            rollback = self.activation.rollback(event.capability_id, reason="v66_statistical_canary_regression", evidence=evidence)
            out["rollback_result"] = rollback
            if rollback.get("rolled_back"):
                out["demotion"] = self.feedback.record(
                    capability_id=event.capability_id, candidate_digest=event.candidate_digest,
                    reason="v66_statistical_canary_regression", evidence=copy.deepcopy(out))
                q = self.quarantine.record_failure(
                    event_id=f"rollback:{event.event_id}", capability_id=event.capability_id,
                    candidate_digest=event.candidate_digest, reason="v66_statistical_canary_regression",
                    family=event.family)
                out["quarantine"] = q
                self.matrix.record_control(capability_id=event.capability_id, candidate_digest=event.candidate_digest,
                                           kind="rollback", payload=copy.deepcopy(out))
                if q["quarantined"]:
                    out["repair_request"] = self.repair.emit(
                        capability_id=event.capability_id, candidate_digest=event.candidate_digest,
                        reason="v66_statistical_canary_regression", family=event.family,
                        evidence={"candidate_failures": q["candidate_failures"], "family_failures": q["family_failures"],
                                  "decision": evidence})
                self.controller.mark_rolled_back(event.capability_id, event.candidate_digest,
                                                 quarantined=bool(q["quarantined"]))
        return out

    def release_quarantine(self, *, capability_id: str, candidate_digest: str, evidence_sha256: str,
                           holdout_score: float, baseline_score: float, verified: bool,
                           untouched_holdout: bool, family: str = "", scope: str = "candidate") -> Dict[str, Any]:
        out = self.quarantine.release_with_holdout(
            capability_id=capability_id, candidate_digest=candidate_digest, evidence_sha256=evidence_sha256,
            holdout_score=holdout_score, baseline_score=baseline_score, verified=verified,
            untouched_holdout=untouched_holdout, family=family, scope=scope)
        if out.get("released"):
            out["canary_reset"] = self.controller.reset_after_release(capability_id, candidate_digest)
            self.matrix.record_control(capability_id=capability_id, candidate_digest=candidate_digest,
                                       kind="quarantine_release", payload=copy.deepcopy(out))
        return out
