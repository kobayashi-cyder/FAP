from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional

from .failure_analyzer import FailureClusterAnalyzer
from .lifecycle import VerificationLifecycle
from .models import ImprovementBudget, LifecycleRecord
from .priority_engine import CapabilityPriorityEngine
from .resource_meter import measure_resources


class AutonomousCapabilityLoop:
    """Minimum working autonomous capability loop.

    Integration policy:
    - Reads benchmark outcomes and selects a gap.
    - Reuses existing Skill Factory/Registry through bridges.
    - Never imports a factory artifact by itself.
    - Requires verifier + dev + untouched holdout evidence before consolidation/registration.
    """

    def __init__(self, benchmark_runner, skill_factory=None, verifier=None, registry=None,
                 analyzer=None, priority_engine=None, lifecycle=None,
                 budget: Optional[ImprovementBudget] = None):
        self.benchmark_runner = benchmark_runner
        self.skill_factory = skill_factory
        self.verifier = verifier
        self.registry = registry
        self.analyzer = analyzer or FailureClusterAnalyzer()
        self.priority_engine = priority_engine or CapabilityPriorityEngine()
        self.budget = budget or ImprovementBudget()
        self.lifecycle = lifecycle or VerificationLifecycle(self.budget)
        self.records: Dict[str, LifecycleRecord] = {}

    def diagnose(self) -> Dict[str, Any]:
        with measure_resources() as metrics:
            dev = list(self.benchmark_runner.run("dev"))
            clusters = self.analyzer.cluster(dev)
            existing = {}
            cost_hints = {}
            prelim = self.priority_engine.from_clusters(clusters, len(dev))
            if self.skill_factory:
                for c in prelim:
                    match = self.skill_factory.existing_skill_for(c.capability_id)
                    if match:
                        existing[c.metadata["cluster_key"]] = match
                    est = self.skill_factory.estimate_cost(c) or {}
                    if est:
                        cost_hints[c.metadata["cluster_key"]] = est
            candidates = self.priority_engine.from_clusters(clusters, len(dev), cost_hints, existing)
            ranked = self.priority_engine.rank(candidates)
        return {
            "dev": self._score_summary(dev),
            "clusters": [c.to_dict() for c in clusters],
            "priorities": [d.to_dict() for d in ranked],
            "selected": ranked[0].to_dict() if ranked else None,
            "diagnostic_resources": metrics,
        }

    def cycle_once(self) -> Dict[str, Any]:
        diagnosis = self.diagnose()
        selected = diagnosis["selected"]
        if not selected:
            return {**diagnosis, "status": "no_failure_cluster"}
        if self.skill_factory is None or self.verifier is None:
            return {**diagnosis, "status": "candidate_selected_bridge_required"}

        capability_id = selected["capability_id"]
        decision = next(d for d in self.priority_engine.rank(
            self.priority_engine.from_clusters(
                self.analyzer.cluster(list(self.benchmark_runner.run("dev"))),
                len(list(self.benchmark_runner.run("dev"))) or 1
            )
        ) if d.candidate.capability_id == capability_id)

        artifact = self.skill_factory.create_candidate(decision.candidate, asdict(self.budget))
        verification = self.verifier.verify(artifact, capability_id=capability_id)
        if not verification.get("static_safe", False) or not verification.get("unit_pass", False) or not verification.get("sandbox_pass", False):
            return {**diagnosis, "status": "candidate_rejected_prebenchmark", "verification": verification}

        dev_after = list(self.benchmark_runner.run("dev"))
        holdout = list(self.benchmark_runner.run("holdout"))
        dev_score = self._score_summary(dev_after)["score"]
        holdout_score = self._score_summary(holdout)["score"]
        baseline_dev = diagnosis["dev"]["score"]
        regression_delta = min(0.0, dev_score - baseline_dev)
        resources = verification.get("resources", {})
        ram_value = resources.get("ram_mb")
        resource_ok = (
            ram_value is not None
            and float(resources.get("code_kb", 0)) <= self.budget.max_generated_code_kb
            and float(ram_value) <= self.budget.max_ram_mb
            and float(resources.get("disk_mb", 0)) <= self.budget.max_disk_mb
            and float(resources.get("test_seconds", 0)) <= self.budget.max_test_seconds
        )
        record = self.records.setdefault(capability_id, LifecycleRecord(capability_id=capability_id))
        self.lifecycle.observe(
            record,
            success=bool(verification.get("verified_success", holdout_score > 0.0)),
            confidence=float(verification.get("confidence", 0.0)),
            dev_score=dev_score,
            holdout_score=holdout_score,
            regression_delta=regression_delta,
            resource_ok=resource_ok,
        )
        registered = False
        if record.state == "consolidated" and self.registry is not None:
            registered = bool(self.registry.register_verified(
                capability_id, artifact,
                {"verification": verification, "dev": self._score_summary(dev_after),
                 "holdout": self._score_summary(holdout), "lifecycle": self.lifecycle.as_dict(record)}
            ))
        return {
            **diagnosis,
            "status": "candidate_evaluated",
            "verification": verification,
            "dev_after": self._score_summary(dev_after),
            "holdout": self._score_summary(holdout),
            "lifecycle": self.lifecycle.as_dict(record),
            "registered": registered,
        }

    @staticmethod
    def _score_summary(results: Iterable) -> Dict[str, Any]:
        rows = list(results)
        n = len(rows)
        ok = sum(1 for r in rows if r.success)
        teacher = sum(1 for r in rows if r.teacher_used)
        latency = sum(r.latency_ms for r in rows) / n if n else 0.0
        return {
            "cases": n, "passed": ok, "failed": n - ok,
            "score": ok / n if n else 0.0,
            "teacher_dependency": teacher / n if n else 0.0,
            "mean_latency_ms": latency,
        }
