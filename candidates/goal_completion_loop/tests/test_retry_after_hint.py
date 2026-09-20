import unittest

from fap_goal_loop.goal_loop import ExecutionResult, GoalSpec, GoalState, PlannedAction
from fap_goal_loop.resilient_capability import CapabilityRetryPolicy, ResilientCapabilityExecutor


def action():
    return PlannedAction(action_id="ra1", kind="read", instruction="read")


def state():
    return GoalState(goal=GoalSpec(goal_id="g1", objective="test", success_criteria=("done",)))


class RetryAfterHintTests(unittest.TestCase):
    def test_provider_hint_can_raise_delay_but_stays_bounded(self):
        policy = CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=2)
        self.assertEqual(policy.delay_before_attempt(1, retry_after_seconds=10), 10.0)
        self.assertEqual(policy.delay_before_attempt(1, retry_after_seconds=90), 60.0)
        self.assertEqual(
            policy.delay_before_attempt(1, elapsed_delay=235, retry_after_seconds=90),
            5.0,
        )

    def test_malformed_provider_hint_is_ignored(self):
        policy = CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=2)
        for hint in ("later", -1, float("inf"), float("nan")):
            self.assertEqual(policy.delay_before_attempt(1, retry_after_seconds=hint), 2.0)

    def test_executor_honors_retry_after_metadata(self):
        calls, delays = [], []

        def handler(instruction, metadata, goal_state):
            calls.append(1)
            if len(calls) == 1:
                return ExecutionResult(
                    "failed",
                    error="rate_limited",
                    metadata={"transient": True, "retry_after_seconds": 7},
                )
            return "recovered"

        executor = ResilientCapabilityExecutor(
            {"read": handler},
            retry_policies={
                "read": CapabilityRetryPolicy(
                    2,
                    True,
                    "read only",
                    retry_delay_seconds=1,
                    max_total_delay_seconds=20,
                )
            },
            sleeper=delays.append,
        )
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["attempts"], 2)
        self.assertEqual(result.metadata["retry_delay_seconds"], 7.0)
        self.assertEqual(delays, [7.0])


if __name__ == "__main__":
    unittest.main()
