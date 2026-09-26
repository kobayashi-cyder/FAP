from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Callable, Mapping

from fap_exponential_linear import budget_for_demand, estimate_interaction_demand
from fap_interaction_fabric import (
    InteractionDispatch,
    InteractionFabric,
    InteractionRequest,
)


_SAFE_REASON = re.compile(r"^[0-9A-Za-z_.:-]{0,160}$")


@dataclass(frozen=True)
class InteractionHandoff:
    request: InteractionRequest
    allow_endpoint_ids: tuple[str, ...] = ()
    reason: str = ""


HandoffPolicy = Callable[
    [InteractionRequest, InteractionDispatch, int],
    InteractionHandoff | None,
]


@dataclass(frozen=True)
class InteractionChainStep:
    index: int
    endpoint_id: str
    dispatch_state: str
    handoff_reason: str = ""


@dataclass(frozen=True)
class InteractionChainResult:
    contract: str
    state: str
    reason: str
    steps: tuple[InteractionChainStep, ...]
    final_payload: dict[str, Any] | None
    max_steps: int

    def to_dict(self) -> dict:
        return {
            "contract": self.contract,
            "state": self.state,
            "reason": self.reason,
            "steps": [asdict(step) for step in self.steps],
            "final_payload": (
                dict(self.final_payload)
                if self.final_payload is not None
                else None
            ),
            "max_steps": self.max_steps,
        }


class InteractionChainCoordinator:
    """Bounded cooperative endpoint handoff over InteractionFabric.

    Endpoint handlers never gain direct routing authority. A separate trusted
    HandoffPolicy decides whether another step is useful and can optionally
    restrict the next step to an explicit endpoint allowlist.
    """

    CONTRACT = "fap.interaction.chain.v1"

    def __init__(
        self,
        fabric: InteractionFabric,
        *,
        max_steps: int = 12,
        allow_revisit: bool = False,
        max_history_turns: int = 128,
    ) -> None:
        if not isinstance(fabric, InteractionFabric):
            raise TypeError("fabric must be InteractionFabric")
        if not 1 <= int(max_steps) <= 32:
            raise ValueError("max_steps must be in [1, 32]")
        if not 1 <= int(max_history_turns) <= 512:
            raise ValueError("max_history_turns must be in [1, 512]")
        self.fabric = fabric
        self.max_steps = int(max_steps)
        self.allow_revisit = bool(allow_revisit)
        self.max_history_turns = int(max_history_turns)

    def run(
        self,
        initial: InteractionRequest,
        policy: HandoffPolicy,
    ) -> InteractionChainResult:
        if not isinstance(initial, InteractionRequest):
            raise TypeError("initial must be InteractionRequest")
        if not callable(policy):
            raise TypeError("policy must be callable")

        demand = estimate_interaction_demand(
            initial.text,
            history_turns=len(initial.history),
            pressure_hint=initial.pressure_hint,
        )
        initial_budget = budget_for_demand(demand, policy=self.fabric.policy)
        step_limit = min(self.max_steps, max(1, initial_budget.reasoning_steps))

        current = initial
        allow: tuple[str, ...] | None = None
        visited: set[str] = set()
        steps: list[InteractionChainStep] = []
        final_payload: dict[str, Any] | None = None

        for index in range(step_limit):
            validation = self._validate_request(current, initial_budget.context_chars)
            if validation:
                return self._result(
                    "blocked",
                    validation,
                    steps,
                    final_payload,
                    step_limit,
                )

            excluded = ()
            if not self.allow_revisit:
                excluded = tuple(sorted(visited))

            dispatch = self.fabric.dispatch(
                current,
                allow_endpoint_ids=allow,
                exclude_endpoint_ids=excluded,
            )
            if dispatch.state != "handled" or dispatch.payload is None:
                state = "partial" if final_payload is not None else dispatch.state
                return self._result(
                    state,
                    "handoff_unhandled" if final_payload is not None else "initial_unhandled",
                    steps,
                    final_payload,
                    step_limit,
                )

            final_payload = dict(dispatch.payload)
            visited.add(dispatch.endpoint_id)

            try:
                handoff = policy(current, dispatch, index)
            except Exception as exc:
                steps.append(
                    InteractionChainStep(
                        index=index,
                        endpoint_id=dispatch.endpoint_id,
                        dispatch_state=dispatch.state,
                    )
                )
                return self._result(
                    "blocked",
                    f"handoff_policy_failed:{type(exc).__name__}",
                    steps,
                    final_payload,
                    step_limit,
                )

            if handoff is None:
                steps.append(
                    InteractionChainStep(
                        index=index,
                        endpoint_id=dispatch.endpoint_id,
                        dispatch_state=dispatch.state,
                    )
                )
                return self._result(
                    "completed",
                    "chain_complete",
                    steps,
                    final_payload,
                    step_limit,
                )

            try:
                self._validate_handoff(handoff)
            except Exception as exc:
                steps.append(
                    InteractionChainStep(
                        index=index,
                        endpoint_id=dispatch.endpoint_id,
                        dispatch_state=dispatch.state,
                    )
                )
                return self._result(
                    "blocked",
                    f"handoff_rejected:{type(exc).__name__}",
                    steps,
                    final_payload,
                    step_limit,
                )

            steps.append(
                InteractionChainStep(
                    index=index,
                    endpoint_id=dispatch.endpoint_id,
                    dispatch_state=dispatch.state,
                    handoff_reason=handoff.reason,
                )
            )
            current = handoff.request
            allow = handoff.allow_endpoint_ids or None

        return self._result(
            "partial",
            "chain_step_limit_reached",
            steps,
            final_payload,
            step_limit,
        )

    def _validate_request(
        self,
        request: InteractionRequest,
        max_chars: int,
    ) -> str:
        if not isinstance(request, InteractionRequest):
            return "handoff_request_type_invalid"
        if len(str(request.text or "")) > max_chars:
            return "handoff_text_exceeds_context_budget"
        if len(request.history) > self.max_history_turns:
            return "handoff_history_exceeds_limit"
        return ""

    @staticmethod
    def _validate_handoff(handoff: InteractionHandoff) -> None:
        if not isinstance(handoff, InteractionHandoff):
            raise TypeError("policy must return InteractionHandoff or None")
        if not isinstance(handoff.request, InteractionRequest):
            raise TypeError("handoff request must be InteractionRequest")
        if not isinstance(handoff.allow_endpoint_ids, tuple):
            raise TypeError("allow_endpoint_ids must be tuple")
        reason = str(handoff.reason or "")
        if not _SAFE_REASON.fullmatch(reason):
            raise ValueError("handoff reason must be a safe bounded code")

    def _result(
        self,
        state: str,
        reason: str,
        steps: list[InteractionChainStep],
        payload: dict[str, Any] | None,
        step_limit: int,
    ) -> InteractionChainResult:
        return InteractionChainResult(
            contract=self.CONTRACT,
            state=state,
            reason=reason,
            steps=tuple(steps),
            final_payload=payload,
            max_steps=step_limit,
        )
