from __future__ import annotations

import copy
from dataclasses import asdict


class V64Coordinator:
    def __init__(self, *, dispatcher, observer, activation_manager, feedback):
        self.dispatcher = dispatcher
        self.observer = observer
        self.activation = activation_manager
        self.feedback = feedback

    def route(self, capability_id, request_id, canary_ratio, baseline=None):
        return self.dispatcher.route(capability_id, request_id=request_id,
                                     canary_ratio=canary_ratio, baseline=baseline)

    def observe(self, *, event_id, capability_id, candidate_digest, arm, verified,
                success, quality, latency_ms):
        inserted = self.observer.ingest(
            event_id=event_id, capability_id=capability_id,
            candidate_digest=candidate_digest, arm=arm, verified=verified,
            success=success, quality=quality, latency_ms=latency_ms,
        )
        decision = self.observer.decide(capability_id=capability_id,
                                        candidate_digest=candidate_digest)
        out = asdict(decision); out['inserted'] = inserted
        if decision.rollback:
            rollback = self.activation.rollback(
                capability_id, reason='v64_ab_regression', evidence=copy.deepcopy(out))
            out['rollback_result'] = rollback
            if rollback.get('rolled_back'):
                evidence_snapshot = copy.deepcopy(out)
                out['demotion'] = self.feedback.record(
                    capability_id=capability_id, candidate_digest=candidate_digest,
                    reason='v64_ab_regression', evidence=evidence_snapshot)
        return out
