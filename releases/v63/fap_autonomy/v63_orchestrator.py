from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from .activation import AtomicActivationManager
from .post_activation_monitor import PostActivationMonitor
from .provenance import PatchHistory


class V63Orchestrator:
    """Connect factory output, V62 promotion, activation, monitoring and rollback."""

    def __init__(self, *, pipeline, registry, activation: AtomicActivationManager,
                 monitor: PostActivationMonitor, history: PatchHistory):
        self.pipeline = pipeline
        self.registry = registry
        self.activation = activation
        self.monitor = monitor
        self.history = history

    def evaluate_candidate(self, *, capability_id: str, artifact: Dict[str, Any], trial_id: str,
                           baseline_dev_score: float, min_dev_gain: float = 0.0,
                           min_holdout_score: float = 0.5) -> Dict[str, Any]:
        result = self.pipeline.evaluate_once(
            capability_id=capability_id, artifact=artifact, trial_id=trial_id,
            baseline_dev_score=baseline_dev_score, min_dev_gain=min_dev_gain,
            min_holdout_score=min_holdout_score,
        )
        self.history.append("candidate_evaluation", {"capability_id": capability_id, "trial_id": trial_id,
                                                       "status": result.get("status"),
                                                       "candidate_digest": result.get("candidate_digest"),
                                                       "lifecycle": result.get("lifecycle")})
        if result.get("registered"):
            entry = self.registry.get(capability_id)
            activation = self.activation.activate(capability_id=capability_id, artifact=artifact,
                                                  registry_entry=entry, source_release="v63")
            self.history.append("activation", activation)
            result["activation"] = activation
        return result

    def ingest_runtime_outcome(self, *, event_id: str, verified: bool, success: bool, latency_ms: float,
                               baseline_success_rate: float, baseline_latency_ms: float) -> Dict[str, Any]:
        current = self.activation.current()
        if not current:
            return {"status": "no_active_candidate", "rollback": False}
        digest = current["candidate_digest"]
        inserted = self.monitor.ingest(event_id=event_id, candidate_digest=digest, verified=verified,
                                       success=success, latency_ms=latency_ms)
        decision = self.monitor.evaluate(candidate_digest=digest,
                                         baseline_success_rate=baseline_success_rate,
                                         baseline_latency_ms=baseline_latency_ms)
        out = asdict(decision); out["inserted"] = inserted
        if decision.rollback:
            rolled = self.activation.rollback(reason=",".join(decision.reasons))
            self.history.append("rollback", {"decision": out, "activation": rolled})
            out["rollback_activation"] = rolled
        return out
