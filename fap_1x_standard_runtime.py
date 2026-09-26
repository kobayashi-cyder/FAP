from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from fap_1x_runtime import FAP1xRuntime
from fap_1x_reasoning_core import FAP1xGeneralReasoningCore
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
        self.reasoning_core = FAP1xGeneralReasoningCore(self.root)
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
            "evidence-gated-multi-lane-reasoning",
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
            "general_reasoning_core": {
                "candidate_lanes": (
                    "deterministic_physics",
                    "verified_arithmetic",
                    "option_conditioned_science",
                    "local_fact",
                    "rule_verified",
                    "derivation_verified",
                    "hypothesis_provisional",
                )
            },
        }

    def _register_standard_endpoints(self) -> None:
        self.register_endpoint(
            "general_reasoning_core",
            self._general_reasoning_handler,
            probe=self._general_reasoning_probe,
            priority=1.60,
            capabilities=(
                "reasoning",
                "verification",
                "counterexample",
                "multi_candidate",
            ),
            task_families=("math", "science", "general"),
            task_forms=("symbolic", "multi_step", "factual", "multiple_choice"),
            failure_specialties=("verification", "disagreement"),
        )
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

    def _general_reasoning_probe(self, request) -> float:
        return self.reasoning_core.probe(request.text)

    def _general_reasoning_handler(self, request, _budget) -> Mapping[str, Any] | None:
        return self.reasoning_core.solve(request.text, request.history)

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
