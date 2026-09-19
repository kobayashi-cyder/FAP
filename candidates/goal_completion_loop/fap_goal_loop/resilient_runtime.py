from __future__ import annotations

from pathlib import Path
from random import random
from time import sleep
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from .goal_loop import ConversationGoalRunner, GoalCompletionLoop, GoalSpec, GoalState, JSONGoalStateStore, PlannedAction
from .resilient_capability import CapabilityRetryPolicy, ResilientCapabilityExecutor
from .runtime import AutonomousRunResult, StructuredCriticAdapter, StructuredPlannerAdapter, _safe_excerpt


class ResilientAutonomousConversationRuntime:
    """Goal-completion runtime with opt-in, fail-closed capability retries.

    Retry behavior is disabled by default. A capability may be retried only when
    its CapabilityRetryPolicy explicitly declares idempotency and records a
    justification. Approval and blocked results are never replayed by the
    executor. Retry sleeping and jitter are injectable so hosts/tests can control
    waiting without changing retry safety semantics.
    """

    def __init__(
        self,
        *,
        planner_model: Callable[[Dict[str, Any]], Mapping[str, Any]],
        critic_model: Callable[[Dict[str, Any]], Mapping[str, Any]],
        handlers: Mapping[str, Callable[[str, Dict[str, Any], GoalState], Any]],
        retry_policies: Mapping[str, CapabilityRetryPolicy] | None = None,
        retry_sleeper: Callable[[float], None] = sleep,
        retry_jitter_source: Callable[[], float] = random,
        approval_kinds: Iterable[str] = (),
        approval: Optional[Callable[[PlannedAction, GoalState], bool]] = None,
        state_dir: Optional[str | Path] = None,
        capability_selector: Optional[Callable[[GoalSpec, GoalState, frozenset[str]], Iterable[str]]] = None,
    ) -> None:
        planner = StructuredPlannerAdapter(
            planner_model,
            capabilities=handlers.keys(),
            approval_kinds=approval_kinds,
            capability_selector=capability_selector,
        )
        executor = ResilientCapabilityExecutor(
            handlers,
            retry_policies=retry_policies,
            sleeper=retry_sleeper,
            jitter_source=retry_jitter_source,
        )
        critic = StructuredCriticAdapter(critic_model)
        store = JSONGoalStateStore(state_dir) if state_dir is not None else None
        self.loop = GoalCompletionLoop(planner, executor, critic, store=store, approval=approval)
        self.runner = ConversationGoalRunner(self.loop)

    def submit(
        self,
        instruction: str,
        *,
        success_criteria: Iterable[str] = (),
        goal_id: Optional[str] = None,
        resume: bool = True,
        **limits: Any,
    ) -> AutonomousRunResult:
        state = self.runner.submit(
            instruction,
            success_criteria=success_criteria,
            goal_id=goal_id,
            resume=resume,
            **limits,
        )
        last_output = ""
        if state.history:
            last_output = _safe_excerpt(state.history[-1].result.output)
        return AutonomousRunResult(
            status=state.status,
            reason=state.reason,
            progress=state.progress,
            steps=state.steps,
            failures=state.failures,
            goal_id=state.goal.goal_id,
            last_output=last_output,
            state=state,
        )
