from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Optional

from .core import (
    BindingRegistry,
    GenericSkillGraph,
    SkillExecution,
    SkillSpec,
)


@dataclass(frozen=True)
class RoutedSkillExecution:
    skill_id: str
    execution: SkillExecution


class AdaptiveSkillGraphBridge:
    """Register only active V86 generic skills into the V82 sparse router."""

    def __init__(
        self,
        graph: GenericSkillGraph,
        bindings: BindingRegistry,
        *,
        controller=None,
        top_k: int = 2,
    ):
        if controller is None:
            from fap_adaptive_circuits import AdaptiveCircuitController
            controller = AdaptiveCircuitController(top_k=top_k)
        self.graph = graph
        self.bindings = bindings
        self.controller = controller
        self.top_k = max(1, int(top_k))
        self.skill_ids: set[str] = set()

    def sync_active(
        self,
        *,
        allowed_skill_ids: Optional[set[str]] = None,
    ) -> list[str]:
        """Synchronize active skills, optionally restricted to final-adopted IDs."""
        allowed = (
            None
            if allowed_skill_ids is None
            else {str(skill_id) for skill_id in allowed_skill_ids}
        )
        adopted = []
        for record in self.graph.registry.active():
            spec = SkillSpec.from_dict(record["skill"])
            if allowed is not None and spec.skill_id not in allowed:
                continue
            self.skill_ids.add(spec.skill_id)
            if spec.skill_id not in self.controller.registry.specs:
                self.controller.add_circuit(
                    spec.skill_id,
                    tags=tuple(dict.fromkeys((spec.name, spec.ability, *spec.tags))),
                    base_priority=0.18,
                    parameters={
                        "generic_skill": 1.0,
                        "verified_binding_dag": 1.0,
                    },
                )
            circuit = self.controller.registry.get(spec.skill_id)
            if self.controller.verifier.is_eligible(circuit):
                adopted.append(spec.skill_id)
                continue
            evidence = record["evidence"]
            checks = (
                record["stage"] == "active",
                len(spec.nodes) <= 12,
                all(self.bindings.is_eligible(node.binding_id) for node in spec.nodes),
                evidence.get("promotion") == "passed",
                int(evidence.get("shadow_successes", 0)) >= 3,
                evidence.get("deterministic") is True,
                evidence.get("timeout_free") is True,
            )
            digest = sha256(
                json.dumps(
                    evidence,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()[:12]
            passed = self.controller.certify(
                spec.skill_id,
                evidence_id=f"v86-skill-adopt:{spec.skill_id}:{digest}",
                benchmark_score=sum(bool(x) for x in checks) / len(checks),
                static_checks=checks,
                deterministic=True,
            )
            if passed:
                circuit.stage = "consolidated"
                circuit.successes = max(3, circuit.successes)
                adopted.append(spec.skill_id)
        return adopted

    def route(
        self,
        task: str,
        *,
        top_k: Optional[int] = None,
        allowed_skill_ids: Optional[set[str]] = None,
    ):
        self.sync_active(allowed_skill_ids=allowed_skill_ids)
        allowed = (
            None
            if allowed_skill_ids is None
            else {str(skill_id) for skill_id in allowed_skill_ids}
        )
        limit = max(1, int(top_k or self.top_k))
        full = self.controller.route(
            task,
            top_k=max(limit, len(self.controller.registry.specs)),
        )
        selected = tuple(
            choice
            for choice in full.selected
            if (
                choice.circuit_id in self.skill_ids
                and (allowed is None or choice.circuit_id in allowed)
            )
        )[:limit]
        from fap_adaptive_circuits import RouteDecision
        return RouteDecision(full.task, selected)

    def execute(
        self,
        task: str,
        value: Any,
        *,
        top_k: Optional[int] = None,
        allowed_skill_ids: Optional[set[str]] = None,
    ) -> tuple[Any, list[RoutedSkillExecution]]:
        decision = self.route(
            task,
            top_k=top_k,
            allowed_skill_ids=allowed_skill_ids,
        )
        results = [
            RoutedSkillExecution(
                choice.circuit_id,
                self.graph.execute(choice.circuit_id, value),
            )
            for choice in decision.selected
        ]
        return decision, results

    def observe(
        self,
        decision,
        results: list[RoutedSkillExecution],
        *,
        evidence_id: str,
    ) -> bool:
        success = bool(results) and all(
            row.execution.ok and not row.execution.timed_out
            for row in results
        )
        return self.controller.observe(
            decision,
            evidence_id=f"v86-skill-runtime:{evidence_id}",
            reward=1.0 if success else 0.0,
            success=success,
            invariants=(len(results) == len(decision.selected),),
        )
