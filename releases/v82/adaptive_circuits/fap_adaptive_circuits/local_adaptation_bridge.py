from __future__ import annotations

from typing import Optional

from .adaptive import AdaptiveCircuitController


LOCAL_ADAPTATION_CIRCUIT_ID = "local_adaptation"
LOCAL_ADAPTATION_TAGS = (
    "予測", "次入力", "局所学習", "適応", "反例", "失敗", "回避",
    "predictive", "counterexample", "hebbian", "local adaptation",
)


class LocalAdaptationCircuitBridge:
    """Expose the V81 local adaptive core as a verifier-gated sparse specialist."""

    def __init__(
        self,
        core,
        *,
        controller: Optional[AdaptiveCircuitController] = None,
        top_k: int = 2,
    ):
        self.core = core
        self.controller = controller or AdaptiveCircuitController(top_k=top_k)
        self.top_k = max(1, int(top_k))
        self._registered = False

    def register(self) -> bool:
        if LOCAL_ADAPTATION_CIRCUIT_ID not in self.controller.registry.specs:
            self.controller.add_circuit(
                LOCAL_ADAPTATION_CIRCUIT_ID,
                tags=LOCAL_ADAPTATION_TAGS,
                base_priority=0.18,
                parameters={"fixed_reservoir": 1.0, "local_plasticity": 1.0},
            )
        spec = self.controller.registry.get(LOCAL_ADAPTATION_CIRCUIT_ID)
        if self.controller.verifier.is_eligible(spec):
            self._registered = True
            return True

        before_digest = self.core.reservoir.fixed_digest()
        before_evidence = set(self.core.seen_learning_evidence)
        guidance = self.core.guidance("予測 次入力 局所学習 反例")
        after_digest = self.core.reservoir.fixed_digest()
        after_evidence = set(self.core.seen_learning_evidence)
        self.core.reservoir.reset()

        checks = (
            bool(before_digest),
            before_digest == after_digest,
            before_evidence == after_evidence,
            "[FAP local-adaptation guidance]" in guidance,
            "learning=verified_local_only" in guidance,
            callable(getattr(self.core, "learn_transition", None)),
            callable(getattr(self.core, "guidance", None)),
        )
        score = sum(bool(x) for x in checks) / len(checks)
        passed = self.controller.certify(
            LOCAL_ADAPTATION_CIRCUIT_ID,
            evidence_id=f"v82-local-adaptation-cert:{before_digest[:12]}",
            benchmark_score=score,
            static_checks=checks,
            deterministic=before_digest == after_digest,
        )
        if passed:
            spec.stage = "consolidated"
            spec.successes = max(spec.successes, 3)
        self._registered = passed
        return passed

    def is_selected(self, task: str, *, top_k: Optional[int] = None) -> bool:
        if not self.register():
            return False
        decision = self.controller.route(task, top_k=top_k or self.top_k)
        return LOCAL_ADAPTATION_CIRCUIT_ID in decision.circuit_ids

    def guidance_if_routed(self, task: str, *, top_k: Optional[int] = None) -> str:
        if not self.is_selected(task, top_k=top_k):
            return ""
        return self.core.guidance(task)

    def learn_transition(self, **kwargs):
        """Delegate verified local learning to V81; successful evidence strengthens routing memory."""
        result = self.core.learn_transition(**kwargs)
        if result.learned and bool(kwargs.get("success")):
            task = str(kwargs.get("source_text", ""))
            decision = self.controller.route(task, top_k=max(self.top_k, len(self.controller.registry.specs)))
            selected = tuple(
                x for x in decision.selected
                if x.circuit_id == LOCAL_ADAPTATION_CIRCUIT_ID
            )
            if selected:
                from .adaptive import RouteDecision
                self.controller.observe(
                    RouteDecision(task, selected),
                    evidence_id=f"v82-local-success:{kwargs.get('evidence_id')}",
                    reward=1.0,
                    success=True,
                    invariants=(result.learned,),
                )
        return result
