from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from fap_1x_runtime import FAP1xRuntime
from fap_adaptive_reasoning import AdaptiveReasoningGovernor
from fap_interaction_fabric import InteractionDispatch
from fap_knowledge_narrator import KnowledgeNarrator
from fap_response_redundancy import ResponseRedundancyPlanner
from fap_response_series_executor import ResponseSeriesExecutor
from fap_factual_qa import FactualQAOrgan
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_reflective_conversation import ReflectiveConversationOrgan
from fap_semantic_conversation import RuntimeSelfProfile, SemanticConversationRouter


class FAP1xStandardRuntime(FAP1xRuntime):
    """Ready-to-use local 1.x runtime with fail-closed reasoning organs."""

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        memory_root: str | Path | None = None,
        max_history_messages: int = 48,
    ) -> None:
        super().__init__(
            memory_root=memory_root,
            max_history_messages=max_history_messages,
        )
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else Path(__file__).resolve().parent
        )
        self.factual = FactualQAOrgan()
        self.knowledge_narrator = KnowledgeNarrator(self.root)
        self.rule_reasoner = GenericRuleReasoner(self.root)
        self.reflective = ReflectiveConversationOrgan()
        self.semantic_router = SemanticConversationRouter(self.root)
        self.self_profile = RuntimeSelfProfile(self.semantic_router)
        self.response_redundancy = ResponseRedundancyPlanner()
        self.response_series = ResponseSeriesExecutor(self.root)
        self.reasoning_governor = AdaptiveReasoningGovernor()
        self._register_standard_endpoints()

    def capabilities(self) -> tuple[str, ...]:
        caps = [
            "1x-unified-runtime",
            "bounded-session-history",
            "verified-tool-fallback",
            "factual-qa",
            "grounded-knowledge-narration",
            "knowledge-inventory",
            "generic-rule-reasoning",
            "reflective-conversation",
            "semantic-self-profile",
            "speech-boundary",
            "repository-coding-adapter",
            "adaptive-response-redundancy:128-lanes",
            "response-synthesis-committee:16-max",
            f"response-specialists:{len(self.response_series.SAFE_SPECIALISTS)}-readonly",
            "verified-specialist-answer-takeover",
            "deterministic-complementary-synthesis",
            "adaptive-reasoning-governor",
            "counterexample-escalation",
            "confidence-calibration",
            "multi-intent-subproblem-reasoning",
            "partial-answer-takeover-guard",
            "fail-closed-epistemics",
        ]
        if self.memory is not None:
            caps.append("semantic-memory")
        return tuple(caps)

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "runtime": "standard",
            "endpoint_ids": self.fabric.endpoint_ids,
            "capabilities": self.capabilities(),
            "knowledge_narrator": {
                "contract": self.knowledge_narrator.CONTRACT,
                "inventory": self.knowledge_narrator.inventory(),
            },
            "generic_rule_reasoner": {
                "entities": len(self.rule_reasoner.entities),
                "relations": len(self.rule_reasoner.relations),
                "rules": len(self.rule_reasoner.rules),
            },
            "semantic_conversation": {
                "intents": len(self.semantic_router.intents),
                "groups": len(self.semantic_router.groups),
            },
            "semantic_memory": self.memory is not None,
            "response_intelligence": {
                "enabled": True,
                "planning_contract": self.response_redundancy.CONTRACT,
                "execution_contract": self.response_series.CONTRACT,
                "max_lanes": self.response_redundancy.MAX_LANES,
                "max_synthesis_width": self.response_redundancy.MAX_SYNTHESIS,
                "safe_specialists": list(self.response_series.SAFE_SPECIALISTS),
                "side_effecting_specialists_redundantly_executed": False,
                "native_revision": "1.0.01-cpp-native-r008",
                "governor_contract": self.reasoning_governor.CONTRACT,
                "subproblem_contract": self.response_series.subproblem.CONTRACT,
                "max_escalation_passes": self.reasoning_governor.MAX_ESCALATION_PASSES,
                "confidence_calibrated": True,
                "fail_closed": True,
            },
        }

    def dispatch(
        self,
        text: str,
        *,
        history: tuple[Mapping[str, Any], ...] = (),
        channel: str = "chat",
        pressure_hint: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> InteractionDispatch:
        primary = super().dispatch(
            text,
            history=history,
            channel=channel,
            pressure_hint=pressure_hint,
            metadata=metadata,
        )
        if channel != "chat":
            return primary

        primary_payload = dict(primary.payload or {})
        primary_reply = self._payload_text(primary_payload)
        if primary_reply and "reply" not in primary_payload:
            primary_payload["reply"] = primary_reply
        primary_payload.setdefault("ok", primary.state == "handled")

        try:
            confidence = float(primary_payload.get(
                "confidence",
                0.78 if primary.state == "handled" else 0.20,
            ))
        except (TypeError, ValueError, OverflowError):
            confidence = 0.50
        confidence = min(1.0, max(0.0, confidence))

        uncertainty = min(
            1.0,
            max(
                0.0,
                (1.0 - confidence)
                + 0.20 * float(primary.demand.value)
                + (0.18 if primary.state != "handled" else 0.0),
            ),
        )
        disagreement = primary.state != "handled" or any(
            attempt.state not in {"handled", "declined"}
            for attempt in primary.attempts
        )

        plan = self.response_redundancy.plan(
            str(text),
            uncertainty=uncertainty,
            confidence=confidence,
            disagreement=disagreement,
            counterexample=False,
            route_candidates=min(8, max(1, int(primary.budget.route_candidates))),
            verification_depth=min(
                6,
                max(1, 1 + int(primary.budget.reasoning_steps) // 20),
            ),
            retries=min(4, max(0, int(primary.budget.repair_rounds))),
            intent_count=self.reasoning_governor.intent_count(str(text)),
            has_route=primary.state == "handled",
        )
        enhanced = self.response_series.run(
            str(text),
            list(history),
            primary_payload,
            plan,
        )
        enhanced["response_redundancy"] = plan.to_dict()

        reply = self._payload_text(enhanced)
        if not reply:
            return primary

        first_execution = enhanced.get("response_series_execution")
        first_selected = (
            str(first_execution.get("selected") or "primary")
            if isinstance(first_execution, Mapping)
            else "primary"
        )
        endpoint_id = (
            primary.endpoint_id
            if first_selected == "primary"
            else "response_series"
        )

        assessment = self.reasoning_governor.assess(
            str(text),
            enhanced,
            dispatch_state=primary.state,
        )
        assessments = [assessment]
        best = enhanced
        best_score = self.reasoning_governor.quality_score(best)
        passes = 1

        escalation_budget = min(
            self.reasoning_governor.MAX_ESCALATION_PASSES,
            max(0, int(assessment.escalation_level)),
        )
        current_assessment = assessment

        for pass_index in range(1, escalation_budget + 1):
            if (
                current_assessment.selected_verified
                and current_assessment.confidence >= 0.90
                and current_assessment.disagreement_count == 0
                and current_assessment.requirement_coverage >= 0.90
                and current_assessment.segment_coverage >= 0.90
            ):
                break

            stronger = self.response_redundancy.plan(
                str(text),
                **self.reasoning_governor.escalation_plan_kwargs(
                    current_assessment,
                    pass_index,
                ),
            )
            candidate = self.response_series.run(
                str(text),
                list(history),
                best,
                stronger,
            )
            candidate["response_redundancy"] = stronger.to_dict()

            candidate_assessment = self.reasoning_governor.assess(
                str(text),
                candidate,
                dispatch_state="handled",
            )
            assessments.append(candidate_assessment)
            passes += 1

            candidate_score = self.reasoning_governor.quality_score(candidate)
            verified_gain = (
                candidate_assessment.selected_verified
                and not current_assessment.selected_verified
            )
            coverage_gain = (
                candidate_assessment.requirement_coverage
                    > current_assessment.requirement_coverage + 0.08
                or candidate_assessment.segment_coverage
                    > current_assessment.segment_coverage + 0.08
            )
            lower_risk = (
                candidate_assessment.epistemic_risk
                < current_assessment.epistemic_risk - 0.06
            )

            if (
                candidate_score > best_score + 0.005
                or verified_gain
                or coverage_gain
                or lower_risk
            ):
                best = candidate
                best_score = candidate_score
                execution = candidate.get("response_series_execution")
                selected = (
                    str(execution.get("selected") or "primary")
                    if isinstance(execution, Mapping)
                    else "primary"
                )
                if selected != "primary":
                    endpoint_id = "response_series"

            current_assessment = candidate_assessment

        final_payload = self.reasoning_governor.calibrate(
            str(text),
            best,
            dispatch_state="handled",
            passes=passes,
            assessments=assessments,
        )

        return InteractionDispatch(
            contract=primary.contract,
            state="handled",
            endpoint_id=endpoint_id,
            demand=primary.demand,
            budget=primary.budget,
            attempts=primary.attempts,
            payload=final_payload,
        )

    def _register_standard_endpoints(self) -> None:
        self.register_endpoint(
            "runtime_profile",
            self._profile_handler,
            probe=self._profile_probe,
            priority=1.40,
            capabilities=("self_profile", "conversation"),
            task_families=("conversation",),
        )
        self.register_endpoint(
            "factual_qa",
            self._factual_handler,
            probe=self._factual_probe,
            priority=1.30,
            capabilities=("facts", "verification"),
            task_families=("science", "general"),
            task_forms=("factual",),
        )
        self.register_endpoint(
            "knowledge_narrator",
            self._knowledge_handler,
            probe=self._knowledge_probe,
            priority=1.15,
            capabilities=("knowledge", "grounding", "explanation"),
            task_families=("science", "general"),
            task_forms=("reading", "factual", "multi_step"),
        )
        self.register_endpoint(
            "rule_reasoner",
            self._rule_handler,
            probe=self._rule_probe,
            priority=1.20,
            capabilities=("logic", "derivation", "verification"),
            task_families=("math", "science", "general"),
            task_forms=("symbolic", "multi_step"),
        )
        self.register_endpoint(
            "reflective",
            self._reflective_handler,
            probe=self._reflective_probe,
            priority=0.80,
            capabilities=("conversation", "reasoning"),
            task_families=("conversation", "general"),
            task_forms=("reading", "multi_step"),
        )

    def _profile_probe(self, request) -> float:
        return 1.0 if self.semantic_router.match(request.text) is not None else 0.0

    def _profile_handler(self, request, _budget) -> Mapping[str, Any] | None:
        return self.self_profile.run(
            request.text,
            version=self.VERSION,
            capabilities=self.capabilities(),
            status=self.status(),
        )

    def _factual_probe(self, request) -> float:
        return 1.0 if self.factual.match(request.text) is not None else 0.0

    def _factual_handler(self, request, _budget) -> Mapping[str, Any] | None:
        return self.factual.run(request.text)

    def _knowledge_probe(self, request) -> float:
        return self.knowledge_narrator.probe(
            request.text,
            list(request.history),
        )

    def _knowledge_handler(self, request, _budget) -> Mapping[str, Any] | None:
        return self.knowledge_narrator.run(
            request.text,
            list(request.history),
        )

    def _rule_probe(self, request) -> float:
        relation = self.rule_reasoner._resolve_relation(request.text)
        return 0.92 if relation is not None else 0.0

    def _rule_handler(self, request, _budget) -> Mapping[str, Any] | None:
        return self.rule_reasoner.run(request.text, list(request.history))

    def _reflective_probe(self, request) -> float:
        concept, score = self.reflective._match(request.text)
        if concept is not None and score > 0:
            return 0.72
        if self.reflective.PREMISE_REASONING.search(request.text):
            return 0.60
        if self.reflective.FOLLOWUP.fullmatch(request.text):
            return 0.55
        if self.reflective.CONTEXTUAL_FOLLOWUP.search(request.text):
            return 0.55
        return 0.0

    def _reflective_handler(self, request, _budget) -> Mapping[str, Any] | None:
        return self.reflective.run(request.text, list(request.history))


def build_standard_runtime(
    *,
    root: str | Path | None = None,
    memory_root: str | Path | None = None,
    max_history_messages: int = 48,
) -> FAP1xStandardRuntime:
    return FAP1xStandardRuntime(
        root=root,
        memory_root=memory_root,
        max_history_messages=max_history_messages,
    )
