import unittest

from fap_goal_loop.goal_loop import ExecutionResult, GoalSpec, GoalState, PlannedAction
from fap_goal_loop.resilient_capability import (
    CapabilityRetryPolicy,
    ResilientCapabilityExecutor,
)
from fap_goal_loop.resilient_runtime import ResilientAutonomousConversationRuntime


def action(kind="read"):
    return PlannedAction(action_id="hardening-1", kind=kind, instruction="do it")


def state():
    return GoalState(
        goal=GoalSpec(
            goal_id="g-hardening",
            objective="test retries",
            success_criteria=("done",),
        )
    )


class RetryHardeningV87Tests(unittest.TestCase):
    def test_capped_backoff_preserves_jitter_distribution(self):
        policy = CapabilityRetryPolicy(
            5,
            True,
            "read only",
            retry_delay_seconds=10,
            retry_backoff_multiplier=4,
            retry_jitter_ratio=0.5,
        )
        # attempt 3 has a raw 160-second backoff. The legal capped interval is
        # still distributed rather than collapsing every jitter sample to 60.
        self.assertEqual(policy.delay_before_attempt(3, jitter_unit=0.0), 30.0)
        self.assertEqual(policy.delay_before_attempt(3, jitter_unit=0.5), 45.0)
        self.assertEqual(policy.delay_before_attempt(3, jitter_unit=1.0), 60.0)

    def test_unregistered_capability_has_uniform_terminal_evidence(self):
        executor = ResilientCapabilityExecutor(
            {"read": lambda *_args: "ok"}
        )
        result = executor.execute(action("missing"), state())
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.metadata["attempts"], 0)
        self.assertFalse(result.metadata["retry_safe"])
        self.assertEqual(result.metadata["retry_delay_seconds"], 0.0)
        self.assertEqual(result.metadata["retry_termination"], "blocked")

    def test_success_and_approval_termination_are_distinct(self):
        ok = ResilientCapabilityExecutor(
            {"read": lambda *_args: "payload"}
        ).execute(action(), state())
        self.assertEqual(ok.metadata["retry_termination"], "completed")

        approval = ResilientCapabilityExecutor(
            {
                "read": lambda *_args: ExecutionResult(
                    "needs_approval",
                    metadata={"transient": True},
                )
            },
            retry_policies={
                "read": CapabilityRetryPolicy(
                    2,
                    True,
                    "idempotent test fixture",
                )
            },
        ).execute(action(), state())
        self.assertEqual(approval.metadata["retry_termination"], "needs_approval")
        self.assertEqual(approval.metadata["attempts"], 1)

    def test_non_transient_and_attempt_exhaustion_are_distinct(self):
        terminal = ResilientCapabilityExecutor(
            {
                "read": lambda *_args: ExecutionResult(
                    "failed",
                    error="bad input",
                    metadata={"transient": False},
                )
            },
            retry_policies={
                "read": CapabilityRetryPolicy(2, True, "read only")
            },
        ).execute(action(), state())
        self.assertEqual(
            terminal.metadata["retry_termination"],
            "non_transient_failure",
        )

        exhausted = ResilientCapabilityExecutor(
            {
                "read": lambda *_args: ExecutionResult(
                    "failed",
                    error="busy",
                    metadata={"transient": True},
                )
            },
            retry_policies={
                "read": CapabilityRetryPolicy(2, True, "read only")
            },
        ).execute(action(), state())
        self.assertEqual(
            exhausted.metadata["retry_termination"],
            "attempts_exhausted",
        )
        self.assertEqual(exhausted.metadata["attempts"], 2)

    def test_delay_budget_exhaustion_is_recorded(self):
        delays = []
        calls = []

        def handler(*_args):
            calls.append(1)
            return ExecutionResult(
                "failed",
                error="busy",
                metadata={"transient": True},
            )

        executor = ResilientCapabilityExecutor(
            {"read": handler},
            retry_policies={
                "read": CapabilityRetryPolicy(
                    5,
                    True,
                    "read only",
                    retry_delay_seconds=1,
                    max_total_delay_seconds=1,
                )
            },
            sleeper=delays.append,
        )
        result = executor.execute(action(), state())
        self.assertEqual(result.metadata["retry_termination"], "delay_budget_exhausted")
        self.assertEqual(result.metadata["attempts"], 2)
        self.assertEqual(delays, [1.0])
        self.assertEqual(len(calls), 2)

    @staticmethod
    def planner(_payload):
        return {"actions": [{"kind": "read", "instruction": "read once"}]}

    @staticmethod
    def critic(payload):
        ok = payload["result"]["status"] == "ok"
        return {
            "satisfied": ok,
            "progress": 1.0 if ok else 0.0,
            "reason": "done" if ok else "retry",
            "retryable": True,
            "replan": False,
            "criteria": {"completed": ok},
        }

    def test_runtime_injects_retry_jitter_source(self):
        calls = {"n": 0}
        delays = []

        def read(_instruction, _metadata, _state):
            calls["n"] += 1
            if calls["n"] == 1:
                return ExecutionResult(
                    "failed",
                    error="busy",
                    metadata={"transient": True},
                )
            return "payload"

        runtime = ResilientAutonomousConversationRuntime(
            planner_model=self.planner,
            critic_model=self.critic,
            handlers={"read": read},
            retry_policies={
                "read": CapabilityRetryPolicy(
                    2,
                    True,
                    "read-only operation",
                    retry_delay_seconds=10,
                    retry_jitter_ratio=0.5,
                )
            },
            retry_sleeper=delays.append,
            retry_jitter_source=lambda: 0.0,
        )
        result = runtime.submit(
            "fetch data",
            success_criteria=["completed"],
            max_steps=2,
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(delays, [5.0])
        self.assertEqual(
            result.state.history[-1].result.metadata["retry_delay_seconds"],
            5.0,
        )


if __name__ == "__main__":
    unittest.main()
