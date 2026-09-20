import unittest

from fap_goal_loop.goal_loop import ExecutionResult, GoalSpec, GoalState, PlannedAction
from fap_goal_loop.resilient_capability import CapabilityRetryPolicy, ResilientCapabilityExecutor


def action():
    return PlannedAction(action_id="rt1", kind="read", instruction="read")


def state():
    return GoalState(goal=GoalSpec(goal_id="g1", objective="test", success_criteria=("done",)))


class RetryTerminationEvidenceTests(unittest.TestCase):
    def test_attempt_exhaustion_is_recorded(self):
        executor = ResilientCapabilityExecutor(
            {"read": lambda instruction, metadata, goal_state: ExecutionResult(
                "failed", error="busy", metadata={"transient": True}
            )},
            retry_policies={"read": CapabilityRetryPolicy(2, True, "read only")},
        )
        result = executor.execute(action(), state())
        self.assertEqual(result.metadata["attempts"], 2)
        self.assertEqual(result.metadata["retry_termination"], "attempts_exhausted")

    def test_delay_budget_exhaustion_is_distinct(self):
        calls = []

        def handler(instruction, metadata, goal_state):
            calls.append(1)
            return ExecutionResult("failed", error="busy", metadata={"transient": True})

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
            sleeper=lambda seconds: None,
        )
        result = executor.execute(action(), state())
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.metadata["retry_termination"], "delay_budget_exhausted")

    def test_non_transient_failure_is_recorded(self):
        executor = ResilientCapabilityExecutor(
            {"read": lambda instruction, metadata, goal_state: ExecutionResult("failed", error="bad")},
            retry_policies={"read": CapabilityRetryPolicy(2, True, "read only")},
        )
        result = executor.execute(action(), state())
        self.assertEqual(result.metadata["retry_termination"], "non_transient_failure")

    def test_success_is_recorded_without_changing_status(self):
        executor = ResilientCapabilityExecutor({"read": lambda instruction, metadata, goal_state: "ok"})
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["retry_termination"], "completed")


if __name__ == "__main__":
    unittest.main()
