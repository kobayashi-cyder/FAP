from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Optional

from fap_generic_skill import (
    BindingRegistry,
    GenericSkillFactory,
    SkillExecution,
    SkillSpec,
)


@dataclass(frozen=True)
class DeploymentExecution:
    skill_id: str
    execution: SkillExecution


class VerifiedSkillDeployment:
    """Two-stage deployment gate: local V86 promotion, then global FAP-Eval."""

    def __init__(
        self,
        factory: GenericSkillFactory,
        *,
        controller=None,
        top_k: int = 2,
    ):
        if controller is None:
            from fap_adaptive_circuits import AdaptiveCircuitController
            controller = AdaptiveCircuitController(top_k=top_k)
        self.factory = factory
        self.bindings: BindingRegistry = factory.bindings
        self.controller = controller
        self.top_k = max(1, int(top_k))
        self.staged: set[str] = set()
        self.enabled: set[str] = set()

    def _record(self, skill_id: str) -> tuple[dict, SkillSpec]:
        record = self.factory.registry.get(skill_id)
        if record["stage"] != "active":
            raise ValueError("only locally active V86 skills may be staged")
        spec = SkillSpec.from_dict(record["skill"])
        if any(
            not self.bindings.is_eligible(node.binding_id)
            for node in spec.nodes
        ):
            raise ValueError("skill references ineligible binding")
        return record, spec

    def stage(self, skill_id: str, *, evidence_id: str) -> SkillSpec:
        record, spec = self._record(skill_id)
        evidence = record["evidence"]
        checks = (
            evidence.get("promotion") == "passed",
            evidence.get("deterministic") is True,
            evidence.get("timeout_free") is True,
            int(evidence.get("shadow_successes", 0)) >= 3,
            len(spec.nodes) <= 12,
            all(
                self.bindings.is_eligible(node.binding_id)
                for node in spec.nodes
            ),
        )
        if spec.skill_id not in self.controller.registry.specs:
            self.controller.add_circuit(
                spec.skill_id,
                tags=tuple(dict.fromkeys((spec.name, spec.ability, *spec.tags))),
                base_priority=0.18,
                parameters={
                    "v90_staged_skill": 1.0,
                    "verified_binding_dag": 1.0,
                },
            )
        circuit = self.controller.registry.get(spec.skill_id)
        if circuit.quarantined:
            raise ValueError("skill circuit is quarantined")
        if not self.controller.verifier.is_eligible(circuit):
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
                evidence_id=f"v90-stage:{evidence_id}:{digest}",
                benchmark_score=sum(bool(x) for x in checks) / len(checks),
                static_checks=checks,
                deterministic=True,
            )
            if not passed:
                raise ValueError("skill failed V90 deployment staging")
        circuit.stage = "shadow"
        circuit.successes = max(2, circuit.successes)
        self.staged.add(spec.skill_id)
        return spec

    def accept(self, skill_id: str) -> None:
        if skill_id not in self.staged:
            raise ValueError("skill is not staged")
        circuit = self.controller.registry.get(skill_id)
        if not self.controller.verifier.is_eligible(circuit):
            raise ValueError("staged skill lost verifier eligibility")
        self.staged.remove(skill_id)
        self.enabled.add(skill_id)
        circuit.stage = "consolidated"
        circuit.successes = max(3, circuit.successes)

    def reject(self, skill_id: str) -> None:
        self.staged.discard(skill_id)
        self.enabled.discard(skill_id)
        if skill_id in self.controller.registry.specs:
            circuit = self.controller.registry.get(skill_id)
            circuit.quarantined = True
            self.controller.verifier.revoke(circuit)

    def route(
        self,
        task: str,
        *,
        include_staged: bool = False,
        top_k: Optional[int] = None,
    ):
        allowed = set(self.enabled)
        if include_staged:
            allowed.update(self.staged)
        limit = max(1, int(top_k or self.top_k))
        full = self.controller.route(
            task,
            top_k=max(limit, len(self.controller.registry.specs) or 1),
        )
        selected = tuple(
            choice
            for choice in full.selected
            if choice.circuit_id in allowed
        )[:limit]
        from fap_adaptive_circuits import RouteDecision
        return RouteDecision(full.task, selected)

    def execute(
        self,
        task: str,
        value: Any,
        *,
        include_staged: bool = False,
    ) -> tuple[Any, list[DeploymentExecution]]:
        decision = self.route(task, include_staged=include_staged)
        results = [
            DeploymentExecution(
                choice.circuit_id,
                self.factory.graph.execute(choice.circuit_id, value),
            )
            for choice in decision.selected
        ]
        return decision, results

    def solve(
        self,
        ability: str,
        payload: Any,
        fallback: Callable[[Any], Any],
        *,
        include_staged: bool = False,
    ) -> Any:
        decision, results = self.execute(
            f"{ability} {payload}",
            payload,
            include_staged=include_staged,
        )
        for row in results:
            if row.execution.ok and not row.execution.timed_out:
                return row.execution.output
        return fallback(payload)
