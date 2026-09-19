import unittest

from fap_goal_loop.goal_loop import ExecutionResult, GoalSpec, GoalState, PlannedAction
from fap_goal_loop.resilient_capability import CapabilityRetryPolicy, ResilientCapabilityExecutor


def action():
    return PlannedAction(action_id="j1", kind="read", instruction="read")


def state():
    return GoalState(goal=GoalSpec(goal_id="g1", objective="test", success_criteria=("done",)))


class RetryJitterTests(unittest.TestCase):
    def test_jitter_policy_is_bounded_and_requires_delay(self):
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=1, retry_jitter_ratio=-0.1)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=1, retry_jitter_ratio=0.6)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_jitter_ratio=0.1)
        policy = CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=10, retry_jitter_ratio=0.5)
        self.assertEqual(policy.delay_before_attempt(1, jitter_unit=0.0), 5.0)
        self.assertEqual(policy.delay_before_attempt(1, jitter_unit=1.0), 15.0)
        with self.assertRaises(ValueError):
            policy.delay_before_attempt(1, jitter_unit=1.1)

    def test_injected_jitter_is_deterministic(self):
        calls, delays = [], []
        jitter = iter((0.0, 1.0))
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            if len(calls) < 3:
                return ExecutionResult("failed", error="busy", metadata={"transient": True})
            return "recovered"
        executor = ResilientCapabilityExecutor(
            {"read": handler},
            retry_policies={"read": CapabilityRetryPolicy(3, True, "read only", retry_delay_seconds=10, retry_jitter_ratio=0.5)},
            sleeper=delays.append,
            jitter_source=lambda: next(jitter),
        )
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["attempts"], 3)
        self.assertEqual(result.metadata["retry_delay_seconds"], 20.0)
        self.assertEqual(delays, [5.0, 15.0])

    def test_jitter_never_exceeds_total_delay_budget(self):
        calls, delays = [], []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            return ExecutionResult("failed", error="busy", metadata={"transient": True})
        executor = ResilientCapabilityExecutor(
            {"read": handler},
            retry_policies={"read": CapabilityRetryPolicy(5, True, "read only", retry_delay_seconds=20, retry_jitter_ratio=0.5, max_total_delay_seconds=25)},
            sleeper=delays.append,
            jitter_source=lambda: 1.0,
        )
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.metadata["attempts"], 2)
        self.assertEqual(result.metadata["retry_delay_seconds"], 25.0)
        self.assertEqual(delays, [25.0])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
