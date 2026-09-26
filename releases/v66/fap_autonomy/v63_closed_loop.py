from __future__ import annotations

from typing import Any, Dict, Optional

from .activation_manager import ActivationManager
from .candidate_pipeline import CandidatePromotionPipeline
from .skill_factory_adapter import SkillFactoryOutputAdapter
from .verified_registry import VerifiedSkillRegistry


class V63ClosedLoopCoordinator:
    """Connects an existing Skill Factory output to V62 promotion and safe activation."""

    def __init__(self, *, adapter: SkillFactoryOutputAdapter, pipeline: CandidatePromotionPipeline,
                 registry: VerifiedSkillRegistry, activation: ActivationManager):
        self.adapter = adapter
        self.pipeline = pipeline
        self.registry = registry
        self.activation = activation

    def process_manifest(self, path: str, *, baseline_dev_score: float,
                         min_dev_gain: float = 0.0, min_holdout_score: float = 0.5) -> Dict[str, Any]:
        candidate = self.adapter.load(path)
        capability_id = candidate["capability_id"]
        results = []
        consolidated = False
        digest = None
        for trial in candidate["trials"]:
            artifact = self.adapter.artifact_for_trial(candidate, trial)
            result = self.pipeline.evaluate_once(
                capability_id=capability_id, artifact=artifact, trial_id=trial["trial_id"],
                baseline_dev_score=baseline_dev_score, min_dev_gain=min_dev_gain,
                min_holdout_score=min_holdout_score,
            )
            results.append(result)
            digest = result.get("candidate_digest") or digest
            state = (result.get("lifecycle") or {}).get("state")
            if state == "consolidated":
                consolidated = True
                break

        activation_result = None
        if consolidated:
            entry = self.registry.get(capability_id)
            if not entry:
                return {"status": "consolidated_without_registry_entry", "capability_id": capability_id,
                        "candidate_digest": digest, "trials": results}
            latest_evidence = (entry.get("evidence") or {}).get("latest_evidence") or {}
            baseline_quality = ((latest_evidence.get("holdout") or {}).get("score"))
            activation_result = self.activation.activate_from_registry(
                entry, baseline_quality=baseline_quality,
                baseline_latency_ms=candidate.get("production_baseline_latency_ms"),
            )
        return {
            "status": "activated" if activation_result and activation_result.get("activated") else
                      ("already_active" if activation_result else "not_consolidated"),
            "capability_id": capability_id,
            "candidate_digest": digest,
            "trials": results,
            "activation": activation_result,
        }
