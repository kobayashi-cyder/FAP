from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

from .goal_loop import (
    ConversationGoalRunner,
    Critique,
    ExecutionResult,
    GoalCompletionLoop,
    GoalSpec,
    GoalState,
    JSONGoalStateStore,
    PlannedAction,
)


def _safe_excerpt(value: Any, limit: int = 1800) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    text = str(value)
    if len(text) <= limit:
        return text
    keep = max(0, limit - 1)
    return text[:keep] + "…"


class StructuredPlannerAdapter:
    """Turns a structured model response into bounded PlannedAction objects.

    The injected model may be local or remote. This class does not assume a specific LLM.
    Only registered capability kinds are accepted.
    """

    def __init__(
        self,
        model: Callable[[Dict[str, Any]], Mapping[str, Any]],
        *,
        capabilities: Iterable[str],
        approval_kinds: Iterable[str] = (),
        max_actions_per_plan: int = 6,
        max_instruction_chars: int = 4000,
        capability_selector: Optional[
            Callable[[GoalSpec, GoalState, frozenset[str]], Iterable[str]]
        ] = None,
    ):
        self.model = model
        self.capabilities = frozenset(str(x).strip() for x in capabilities if str(x).strip())
        self.approval_kinds = frozenset(str(x).strip() for x in approval_kinds if str(x).strip())
        self.max_actions_per_plan = max(1, int(max_actions_per_plan))
        self.max_instruction_chars = max(64, int(max_instruction_chars))
        self.capability_selector = capability_selector
        if not self.capabilities:
            raise ValueError("at least one capability is required")
        if not self.approval_kinds.issubset(self.capabilities):
            raise ValueError("approval_kinds must be registered capabilities")

    @staticmethod
    def _history_summary(state: GoalState, limit: int = 6) -> list[dict[str, Any]]:
        rows = []
        for record in state.history[-limit:]:
            rows.append(
                {
                    "step": record.step,
                    "action_id": record.action.action_id,
                    "kind": record.action.kind,
                    "status": record.result.status,
                    "error": record.result.error[:300],
                    "progress": record.critique.progress,
                    "reason": record.critique.reason[:500],
                }
            )
        return rows

    def plan(self, goal: GoalSpec, state: GoalState, hint: str = "") -> Sequence[PlannedAction]:
        active_capabilities = self.capabilities
        if self.capability_selector is not None:
            selected = frozenset(
                str(x).strip()
                for x in self.capability_selector(goal, state, self.capabilities)
                if str(x).strip()
            )
            if not selected:
                raise ValueError("capability selector returned no capabilities")
            if not selected.issubset(self.capabilities):
                raise ValueError("capability selector returned unregistered capability")
            active_capabilities = selected

        payload = {
            "task": "plan_next_actions",
            "goal": {
                "goal_id": goal.goal_id,
                "objective": goal.objective,
                "success_criteria": list(goal.success_criteria),
                "metadata": dict(goal.metadata),
            },
            "state": {
                "progress": state.progress,
                "steps": state.steps,
                "failures": state.failures,
                "no_progress": state.no_progress,
                "replans": state.replans,
            },
            "hint": hint,
            "capabilities": sorted(active_capabilities),
            "recent_history": self._history_summary(state),
            "rules": {
                "return_only_registered_capabilities": True,
                "prefer_fewest_actions": True,
                "mark_irreversible_or_external_actions_for_approval": True,
            },
        }
        raw = self.model(payload)
        if not isinstance(raw, Mapping):
            raise ValueError("planner model must return an object")
        actions = raw.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("planner response requires non-empty actions")
        if len(actions) > self.max_actions_per_plan:
            raise ValueError("planner returned too many actions")

        planned: list[PlannedAction] = []
        for idx, item in enumerate(actions):
            if not isinstance(item, Mapping):
                raise ValueError("each action must be an object")
            kind = str(item.get("kind", "")).strip()
            instruction = str(item.get("instruction", "")).strip()
            if kind not in active_capabilities:
                raise ValueError(f"unsupported or inactive capability: {kind}")
            if not instruction:
                raise ValueError("action instruction is required")
            if len(instruction) > self.max_instruction_chars:
                raise ValueError("action instruction exceeds limit")
            expected = str(item.get("expected_outcome", "")).strip()
            raw_id = str(item.get("action_id", "")).strip()
            if not raw_id:
                seed = f"{goal.goal_id}|{state.steps}|{idx}|{kind}|{instruction}"
                raw_id = "a-" + sha256(seed.encode("utf-8")).hexdigest()[:12]
            metadata = item.get("metadata") or {}
            if not isinstance(metadata, Mapping):
                raise ValueError("action metadata must be an object")
            planned.append(
                PlannedAction(
                    action_id=raw_id,
                    kind=kind,
                    instruction=instruction,
                    expected_outcome=expected,
                    requires_approval=(
                        bool(item.get("requires_approval", False))
                        or kind in self.approval_kinds
                    ),
                    metadata=dict(metadata),
                )
            )
        return planned


class CapabilityRouterExecutor:
    """Routes a planned action to one registered FAP capability handler."""

    def __init__(
        self,
        handlers: Mapping[str, Callable[[str, Dict[str, Any], GoalState], Any]],
    ):
        self.handlers = {str(k): v for k, v in handlers.items()}
        if not self.handlers:
            raise ValueError("at least one handler is required")

    def execute(self, action: PlannedAction, state: GoalState) -> ExecutionResult:
        handler = self.handlers.get(action.kind)
        if handler is None:
            return ExecutionResult(
                "blocked",
                error=f"capability_not_registered:{action.kind}",
            )
        try:
            raw = handler(action.instruction, dict(action.metadata), state)
        except Exception as exc:
            return ExecutionResult(
                "failed",
                error=f"{type(exc).__name__}: {exc}",
                metadata={"handler_exception": True, "kind": action.kind},
            )

        if isinstance(raw, ExecutionResult):
            return raw
        if isinstance(raw, Mapping) and "status" in raw:
            status = str(raw.get("status", ""))
            if status not in {"ok", "failed", "blocked", "needs_approval"}:
                raise ValueError("handler returned invalid status")
            meta = raw.get("metadata") or {}
            if not isinstance(meta, Mapping):
                raise ValueError("handler metadata must be an object")
            return ExecutionResult(
                status=status,
                output=raw.get("output"),
                error=str(raw.get("error", "")),
                metadata=dict(meta),
            )
        return ExecutionResult("ok", output=raw)


class StructuredCriticAdapter:
    """Uses a structured evaluator to decide whether the user's goal is actually done."""

    def __init__(
        self,
        model: Callable[[Dict[str, Any]], Mapping[str, Any]],
        *,
        max_output_excerpt: int = 1800,
    ):
        self.model = model
        self.max_output_excerpt = max(128, int(max_output_excerpt))

    def evaluate(
        self,
        goal: GoalSpec,
        state: GoalState,
        action: PlannedAction,
        result: ExecutionResult,
    ) -> Critique:
        payload = {
            "task": "evaluate_goal_progress",
            "goal": {
                "objective": goal.objective,
                "success_criteria": list(goal.success_criteria),
            },
            "state_before_evaluation": {
                "progress": state.progress,
                "steps": state.steps,
                "failures": state.failures,
            },
            "action": {
                "action_id": action.action_id,
                "kind": action.kind,
                "instruction": action.instruction,
                "expected_outcome": action.expected_outcome,
            },
            "result": {
                "status": result.status,
                "error": result.error[:500],
                "output_excerpt": _safe_excerpt(result.output, self.max_output_excerpt),
                "metadata": dict(result.metadata),
            },
            "rules": {
                "satisfied_only_if_success_criteria_are_met": True,
                "do_not_invent_success": True,
                "request_replan_when_current_route_is_insufficient": True,
            },
        }
        raw = self.model(payload)
        if not isinstance(raw, Mapping):
            raise ValueError("critic model must return an object")
        criteria = raw.get("criteria") or {}
        if not isinstance(criteria, Mapping):
            raise ValueError("critic criteria must be an object")
        return Critique(
            satisfied=bool(raw.get("satisfied", False)),
            progress=float(raw.get("progress", state.progress)),
            reason=str(raw.get("reason", "")).strip() or "critic_no_reason",
            retryable=bool(raw.get("retryable", True)),
            replan=bool(raw.get("replan", False)),
            next_hint=str(raw.get("next_hint", "")).strip(),
            criteria={str(k): bool(v) for k, v in criteria.items()},
        )


@dataclass(frozen=True)
class AutonomousRunResult:
    status: str
    reason: str
    progress: float
    steps: int
    failures: int
    goal_id: str
    last_output: str
    state: GoalState


class AutonomousConversationRuntime:
    """Conversation entry point for bounded long-horizon autonomy.

    One instruction enters the goal loop. The planner chooses registered capabilities,
    the executor calls them, and the critic decides whether to finish or replan.
    """

    def __init__(
        self,
        *,
        planner_model: Callable[[Dict[str, Any]], Mapping[str, Any]],
        critic_model: Callable[[Dict[str, Any]], Mapping[str, Any]],
        handlers: Mapping[str, Callable[[str, Dict[str, Any], GoalState], Any]],
        approval_kinds: Iterable[str] = (),
        approval: Optional[Callable[[PlannedAction, GoalState], bool]] = None,
        state_dir: Optional[str | Path] = None,
        capability_selector: Optional[
            Callable[[GoalSpec, GoalState, frozenset[str]], Iterable[str]]
        ] = None,
    ):
        planner = StructuredPlannerAdapter(
            planner_model,
            capabilities=handlers.keys(),
            approval_kinds=approval_kinds,
            capability_selector=capability_selector,
        )
        executor = CapabilityRouterExecutor(handlers)
        critic = StructuredCriticAdapter(critic_model)
        store = JSONGoalStateStore(state_dir) if state_dir is not None else None
        self.loop = GoalCompletionLoop(
            planner,
            executor,
            critic,
            store=store,
            approval=approval,
        )
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
