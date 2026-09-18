from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence


TERMINAL_STATES = {"completed", "blocked", "failed", "stalled", "exhausted"}


@dataclass(frozen=True)
class GoalSpec:
    """A user objective plus explicit completion boundaries.

    The loop is deliberately provider-agnostic. Planning, execution and evaluation are
    injected so FAP can route easy work locally and hard work to external models/tools.
    """

    goal_id: str
    objective: str
    success_criteria: tuple[str, ...] = ()
    max_steps: int = 12
    max_replans: int = 8
    max_failures: int = 4
    max_no_progress: int = 3
    max_same_action: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.goal_id.strip():
            raise ValueError("goal_id is required")
        if not self.objective.strip():
            raise ValueError("objective is required")
        for name in (
            "max_steps",
            "max_replans",
            "max_failures",
            "max_no_progress",
            "max_same_action",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")


@dataclass(frozen=True)
class PlannedAction:
    action_id: str
    kind: str
    instruction: str
    expected_outcome: str = ""
    requires_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("action_id is required")
        if not self.kind.strip():
            raise ValueError("kind is required")
        if not self.instruction.strip():
            raise ValueError("instruction is required")

    def fingerprint(self) -> str:
        payload = {
            "kind": self.kind,
            "instruction": self.instruction,
            "expected_outcome": self.expected_outcome,
            "metadata": self.metadata,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    output: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"ok", "failed", "blocked", "needs_approval"}:
            raise ValueError("invalid execution status")


@dataclass(frozen=True)
class Critique:
    satisfied: bool
    progress: float
    reason: str
    retryable: bool = True
    replan: bool = False
    next_hint: str = ""
    criteria: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.progress) <= 1.0:
            raise ValueError("progress must be in 0..1")


@dataclass(frozen=True)
class StepRecord:
    step: int
    action: PlannedAction
    result: ExecutionResult
    critique: Critique

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GoalState:
    goal: GoalSpec
    status: str = "running"
    reason: str = ""
    steps: int = 0
    replans: int = 0
    failures: int = 0
    no_progress: int = 0
    progress: float = 0.0
    pending: List[PlannedAction] = field(default_factory=list)
    history: List[StepRecord] = field(default_factory=list)
    action_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": asdict(self.goal),
            "status": self.status,
            "reason": self.reason,
            "steps": self.steps,
            "replans": self.replans,
            "failures": self.failures,
            "no_progress": self.no_progress,
            "progress": self.progress,
            "pending": [asdict(x) for x in self.pending],
            "history": [x.to_dict() for x in self.history],
            "action_counts": dict(self.action_counts),
        }

    @classmethod
    def from_dict(cls, obj: Dict[str, Any]) -> "GoalState":
        goal_raw = dict(obj["goal"])
        goal_raw["success_criteria"] = tuple(goal_raw.get("success_criteria", ()))
        goal = GoalSpec(**goal_raw)
        pending = [PlannedAction(**x) for x in obj.get("pending", [])]
        history = []
        for row in obj.get("history", []):
            history.append(
                StepRecord(
                    step=int(row["step"]),
                    action=PlannedAction(**row["action"]),
                    result=ExecutionResult(**row["result"]),
                    critique=Critique(**row["critique"]),
                )
            )
        return cls(
            goal=goal,
            status=str(obj.get("status", "running")),
            reason=str(obj.get("reason", "")),
            steps=int(obj.get("steps", 0)),
            replans=int(obj.get("replans", 0)),
            failures=int(obj.get("failures", 0)),
            no_progress=int(obj.get("no_progress", 0)),
            progress=float(obj.get("progress", 0.0)),
            pending=pending,
            history=history,
            action_counts={str(k): int(v) for k, v in (obj.get("action_counts") or {}).items()},
        )


class Planner(Protocol):
    def plan(self, goal: GoalSpec, state: GoalState, hint: str = "") -> Sequence[PlannedAction]: ...


class Executor(Protocol):
    def execute(self, action: PlannedAction, state: GoalState) -> ExecutionResult: ...


class Critic(Protocol):
    def evaluate(
        self,
        goal: GoalSpec,
        state: GoalState,
        action: PlannedAction,
        result: ExecutionResult,
    ) -> Critique: ...


class JSONGoalStateStore:
    """Small deterministic checkpoint store for interruption/resume.

    It stores orchestration state only. It never serializes or executes callables.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, goal_id: str) -> Path:
        safe = "".join(ch for ch in goal_id if ch.isalnum() or ch in "-_")
        if not safe or safe != goal_id:
            raise ValueError("goal_id contains unsupported characters")
        return self.root / f"{safe}.json"

    def save(self, state: GoalState) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(state.goal.goal_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path

    def load(self, goal_id: str) -> Optional[GoalState]:
        path = self._path(goal_id)
        if not path.is_file():
            return None
        return GoalState.from_dict(json.loads(path.read_text(encoding="utf-8")))


class GoalCompletionLoop:
    """Plan -> execute -> critic -> replan until the goal is satisfied or bounded.

    This is the missing long-horizon control layer: a single user instruction can keep
    producing the next safe action without requiring a new user message after every step.

    The loop is synchronous. It does not pretend to work in the background. External or
    irreversible actions can mark requires_approval=True and are paused unless an injected
    approval callback explicitly permits them.
    """

    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        critic: Critic,
        *,
        store: Optional[JSONGoalStateStore] = None,
        approval: Optional[Callable[[PlannedAction, GoalState], bool]] = None,
        min_progress_delta: float = 0.01,
    ):
        self.planner = planner
        self.executor = executor
        self.critic = critic
        self.store = store
        self.approval = approval
        self.min_progress_delta = max(0.0, float(min_progress_delta))

    def run(self, goal: GoalSpec, *, resume: bool = True) -> GoalState:
        state = self.store.load(goal.goal_id) if (resume and self.store) else None
        if state is None:
            state = GoalState(goal=goal)
        elif state.goal != goal:
            raise ValueError("stored goal does not match supplied goal")

        if state.status == "paused":
            state.status = "running"
            state.reason = ""
        elif state.status in TERMINAL_STATES:
            return state

        hint = state.history[-1].critique.next_hint if state.history else ""

        while state.status == "running":
            if state.steps >= goal.max_steps:
                return self._finish(state, "exhausted", "max_steps_reached")
            if state.failures >= goal.max_failures:
                return self._finish(state, "failed", "max_failures_reached")
            if state.no_progress >= goal.max_no_progress:
                return self._finish(state, "stalled", "no_progress_limit_reached")

            if not state.pending:
                if state.replans >= goal.max_replans:
                    return self._finish(state, "exhausted", "max_replans_reached")
                planned = list(self.planner.plan(goal, state, hint))
                state.replans += 1
                if not planned:
                    return self._finish(state, "blocked", "planner_returned_no_actions")
                state.pending.extend(planned)
                self._checkpoint(state)

            action = state.pending.pop(0)

            if action.requires_approval:
                if self.approval is None or not bool(self.approval(action, state)):
                    state.pending.insert(0, action)
                    return self._finish(state, "paused", "approval_required")

            fingerprint = action.fingerprint()
            count = state.action_counts.get(fingerprint, 0) + 1
            state.action_counts[fingerprint] = count
            if count > goal.max_same_action:
                return self._finish(state, "stalled", "repeated_action_limit_reached")

            try:
                result = self.executor.execute(action, state)
            except Exception as exc:  # injected adapters must not crash the loop
                result = ExecutionResult(
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    metadata={"executor_exception": True},
                )

            state.steps += 1
            if result.status == "needs_approval":
                state.pending.insert(0, action)
                return self._finish(state, "paused", "executor_requires_approval")
            if result.status == "blocked":
                return self._record_and_finish_blocked(state, action, result)

            try:
                critique = self.critic.evaluate(goal, state, action, result)
            except Exception as exc:
                critique = Critique(
                    satisfied=False,
                    progress=state.progress,
                    reason=f"critic_exception:{type(exc).__name__}",
                    retryable=False,
                    replan=False,
                )

            record = StepRecord(state.steps, action, result, critique)
            state.history.append(record)

            old_progress = state.progress
            state.progress = max(state.progress, float(critique.progress))
            if state.progress >= old_progress + self.min_progress_delta:
                state.no_progress = 0
            else:
                state.no_progress += 1

            if result.status == "failed":
                state.failures += 1

            hint = critique.next_hint
            if critique.satisfied:
                return self._finish(state, "completed", critique.reason or "success_criteria_satisfied")

            if result.status == "failed" and not critique.retryable:
                return self._finish(state, "failed", critique.reason or "non_retryable_failure")

            if critique.replan or result.status == "failed":
                state.pending.clear()

            self._checkpoint(state)

        return state

    def _record_and_finish_blocked(
        self,
        state: GoalState,
        action: PlannedAction,
        result: ExecutionResult,
    ) -> GoalState:
        critique = Critique(
            satisfied=False,
            progress=state.progress,
            reason=result.error or "execution_blocked",
            retryable=False,
        )
        state.history.append(StepRecord(state.steps, action, result, critique))
        return self._finish(state, "blocked", critique.reason)

    def _checkpoint(self, state: GoalState) -> None:
        if self.store is not None:
            self.store.save(state)

    def _finish(self, state: GoalState, status: str, reason: str) -> GoalState:
        state.status = status
        state.reason = reason
        self._checkpoint(state)
        return state


class ConversationGoalRunner:
    """Thin adapter from a chat instruction to the bounded autonomous loop."""

    def __init__(self, loop: GoalCompletionLoop):
        self.loop = loop

    @staticmethod
    def deterministic_goal_id(instruction: str) -> str:
        digest = sha256(instruction.strip().encode("utf-8")).hexdigest()[:16]
        return f"goal-{digest}"

    def submit(
        self,
        instruction: str,
        *,
        success_criteria: Iterable[str] = (),
        goal_id: Optional[str] = None,
        **limits: Any,
    ) -> GoalState:
        text = str(instruction).strip()
        if not text:
            raise ValueError("instruction is required")
        goal = GoalSpec(
            goal_id=goal_id or self.deterministic_goal_id(text),
            objective=text,
            success_criteria=tuple(str(x).strip() for x in success_criteria if str(x).strip()),
            **limits,
        )
        return self.loop.run(goal)
