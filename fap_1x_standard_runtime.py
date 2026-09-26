from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from fap_1x_runtime import FAP1xRuntime
from fap_interaction_fabric import InteractionDispatch
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
        self.rule_reasoner = GenericRuleReasoner(self.root)
        self.reflective = ReflectiveConversationOrgan()
        self.semantic_router = SemanticConversationRouter(self.root)
        self.self_profile = RuntimeSelfProfile(self.semantic_router)
        self.response_redundancy = ResponseRedundancyPlanner()
        self.response_series = ResponseSeriesExecutor(self.root)
        self._register_standard_endpoints()

    def capabilities(self) -> tuple[str, ...]:
        caps = [
            "1x-unified-runtime",
            "bounded-session-history",
            "verified-tool-fallback",
            "factual-qa",
            "generic-rule-reasoning",
            "reflective-conversation",
            "semantic-self-profile",
            "speech-boundary",
            "repository-coding-adapter",
            "adaptive-response-redundancy:128-lanes",
            "response-synthesis-committee:16-max",
            "response-specialists:16-readonly",
            "verified-specialist-answer-takeover",
            "deterministic-complementary-synthesis",
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
            intent_count=0,
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

        execution = enhanced.get("response_series_execution")
        selected = (
            str(execution.get("selected") or "primary")
            if isinstance(execution, Mapping)
            else "primary"
        )
        endpoint_id = primary.endpoint_id if selected == "primary" else "response_series"
        return InteractionDispatch(
            contract=primary.contract,
            state="handled",
            endpoint_id=endpoint_id,
            demand=primary.demand,
            budget=primary.budget,
            attempts=primary.attempts,
            payload=enhanced,
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
