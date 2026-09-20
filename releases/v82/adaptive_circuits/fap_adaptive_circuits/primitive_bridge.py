from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Optional

from .adaptive import AdaptiveCircuitController, RouteDecision


@dataclass(frozen=True)
class PrimitiveExecution:
    primitive_id: str
    ok: bool
    output: Any = None
    timed_out: bool = False
    error: str = ""


class PrimitiveCircuitBridge:
    """Adopt only evidence-promoted V80 primitives into the V82 sparse circuit pool."""

    def __init__(
        self,
        primitive_loop,
        *,
        controller: Optional[AdaptiveCircuitController] = None,
        top_k: int = 2,
    ):
        self.primitive_loop = primitive_loop
        self.skill_registry = primitive_loop.registry
        self.controller = controller or AdaptiveCircuitController(top_k=top_k)
        self.top_k = max(1, int(top_k))
        self.primitive_ids: set[str] = set()

    @staticmethod
    def _tags(record: dict) -> tuple[str, ...]:
        candidate = record.get("candidate", {})
        program = candidate.get("program", [])
        raw = [
            candidate.get("name", ""),
            candidate.get("description", ""),
            candidate.get("input_kind", ""),
            candidate.get("output_kind", ""),
            *[str(x.get("op", "")) for x in program if isinstance(x, dict)],
        ]
        return tuple(dict.fromkeys(x.strip() for x in raw if str(x).strip()))

    @staticmethod
    def _certification_score(record: dict) -> tuple[float, tuple[bool, ...], bool]:
        evidence = record.get("evidence", {})
        unit_total = int(evidence.get("unit_total", 0))
        unit_passed = int(evidence.get("unit_passed", 0))
        shadow = int(evidence.get("shadow_successes", 0))
        deterministic = evidence.get("deterministic") is True
        checks = (
            record.get("stage") == "active",
            unit_total >= 5,
            unit_passed == unit_total,
            evidence.get("boundary_passed") is True,
            deterministic,
            evidence.get("timeout_free") is True,
            shadow >= 3,
        )
        score = sum(bool(x) for x in checks) / len(checks)
        return score, checks, deterministic

    def sync_active(self) -> list[str]:
        """Synchronize V80 SkillRegistry.active() into verifier-approved V82 circuits."""
        adopted: list[str] = []
        for record in self.skill_registry.active():
            pid = str(record["primitive_id"])
            self.primitive_ids.add(pid)
            if pid not in self.controller.registry.specs:
                self.controller.add_circuit(
                    pid,
                    tags=self._tags(record),
                    base_priority=0.18,
                    parameters={"primitive": 1.0, "sandboxed": 1.0},
                )
            spec = self.controller.registry.get(pid)
            if self.controller.verifier.is_eligible(spec):
                adopted.append(pid)
                continue
            score, checks, deterministic = self._certification_score(record)
            evidence_digest = sha256(
                json.dumps(record.get("evidence", {}), ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:12]
            passed = self.controller.certify(
                pid,
                evidence_id=f"v82-primitive-adopt:{pid}:{evidence_digest}",
                benchmark_score=score,
                static_checks=checks,
                deterministic=deterministic,
            )
            if passed:
                # V80 already required at least three successful shadow executions.
                spec.stage = "consolidated"
                spec.successes = max(spec.successes, 3)
                adopted.append(pid)
        return adopted

    def route(self, task: str, *, top_k: Optional[int] = None) -> RouteDecision:
        """Return only primitive circuits, even when the controller also holds other specialists."""
        self.sync_active()
        limit = max(1, int(top_k or self.top_k))
        full = self.controller.route(task, top_k=max(limit, len(self.controller.registry.specs)))
        selected = tuple(x for x in full.selected if x.circuit_id in self.primitive_ids)[:limit]
        return RouteDecision(full.task, selected)

    def execute(self, task: str, value: Any, *, top_k: Optional[int] = None) -> tuple[RouteDecision, list[PrimitiveExecution]]:
        decision = self.route(task, top_k=top_k)
        results: list[PrimitiveExecution] = []
        for choice in decision.selected:
            raw = self.primitive_loop.execute_active(choice.circuit_id, value)
            results.append(
                PrimitiveExecution(
                    primitive_id=choice.circuit_id,
                    ok=bool(raw.ok),
                    output=raw.output,
                    timed_out=bool(raw.timed_out),
                    error=str(raw.error or ""),
                )
            )
        return decision, results

    def observe(
        self,
        decision: RouteDecision,
        results: list[PrimitiveExecution],
        *,
        evidence_id: str,
    ) -> bool:
        if not decision.selected or len(results) != len(decision.selected):
            success = False
        else:
            success = all(x.ok and not x.timed_out for x in results)
        reward = 1.0 if success else 0.0
        return self.controller.observe(
            decision,
            evidence_id=f"v82-primitive-runtime:{evidence_id}",
            reward=reward,
            success=success,
            invariants=(len(results) == len(decision.selected),),
        )
