import pytest

from fap_goal_loop.goal_loop import ExecutionResult, GoalState, PlannedAction
from fap_goal_loop.resilient_capability import CapabilityRetryPolicy, ResilientCapabilityExecutor


def action(kind="read"):
    return PlannedAction(action_id="a1", kind=kind, instruction="do it")


def state():
    return GoalState(goal_id="g1")


def test_retry_policy_is_fail_closed():
    with pytest.raises(ValueError):
        CapabilityRetryPolicy(max_attempts=2)
    with pytest.raises(ValueError):
        CapabilityRetryPolicy(max_attempts=2, idempotent=True)
    with pytest.raises(ValueError):
        CapabilityRetryPolicy(max_attempts=6, idempotent=True, justification="read only")


def test_transient_failure_retries_only_when_explicitly_safe():
    calls = []

    def handler(instruction, metadata, goal_state):
        calls.append(instruction)
        if len(calls) == 1:
            return ExecutionResult("failed", error="timeout", metadata={"transient": True})
        return ExecutionResult("ok", output="recovered")

    executor = ResilientCapabilityExecutor(
        {"read": handler},
        retry_policies={
            "read": CapabilityRetryPolicy(
                max_attempts=2,
                idempotent=True,
                justification="read-only lookup has no external side effects",
            )
        },
    )
    result = executor.execute(action(), state())
    assert result.status == "ok"
    assert result.output == "recovered"
    assert result.metadata["attempts"] == 2
    assert len(calls) == 2


def test_unconfigured_capability_never_retries():
    calls = []

    def handler(instruction, metadata, goal_state):
        calls.append(1)
        return ExecutionResult("failed", error="timeout", metadata={"transient": True})

    result = ResilientCapabilityExecutor({"read": handler}).execute(action(), state())
    assert result.status == "failed"
    assert result.metadata["attempts"] == 1
    assert len(calls) == 1


def test_needs_approval_is_never_retried():
    calls = []

    def handler(instruction, metadata, goal_state):
        calls.append(1)
        return ExecutionResult("needs_approval", metadata={"transient": True})

    executor = ResilientCapabilityExecutor(
        {"write": handler},
        retry_policies={
            "write": CapabilityRetryPolicy(
                max_attempts=3,
                idempotent=True,
                justification="test fixture",
            )
        },
    )
    result = executor.execute(action("write"), state())
    assert result.status == "needs_approval"
    assert result.metadata["attempts"] == 1
    assert len(calls) == 1


def test_non_transient_failure_is_terminal():
    calls = []

    def handler(instruction, metadata, goal_state):
        calls.append(1)
        return ExecutionResult("failed", error="invalid input", metadata={"transient": False})

    executor = ResilientCapabilityExecutor(
        {"read": handler},
        retry_policies={
            "read": CapabilityRetryPolicy(2, True, "read only"),
        },
    )
    result = executor.execute(action(), state())
    assert result.metadata["attempts"] == 1
    assert len(calls) == 1
