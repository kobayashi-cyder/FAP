import unittest

from fap_goal_loop.goal_loop import ExecutionResult, GoalSpec, GoalState, PlannedAction
from fap_goal_loop.resilient_capability import CapabilityRetryPolicy, ResilientCapabilityExecutor


def action(kind="read"):
    return PlannedAction(action_id="a1", kind=kind, instruction="do it")


def state():
    return GoalState(goal=GoalSpec(goal_id="g1", objective="test", success_criteria=("done",)))


class ResilientCapabilityTests(unittest.TestCase):
    def test_retry_policy_is_fail_closed(self):
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(max_attempts=2)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(max_attempts=2, idempotent=True)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(max_attempts=6, idempotent=True, justification="read only")
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(retryable_exceptions=(TimeoutError,))
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retryable_exceptions=(str,))
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=-0.1)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=60.1)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(retry_delay_seconds=1)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_backoff_multiplier=0.9)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_backoff_multiplier=4.1)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_backoff_multiplier=2)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=1, retry_jitter_ratio=-0.1)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=1, retry_jitter_ratio=0.6)
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_jitter_ratio=0.1)

    def test_transient_failure_retries_only_when_explicitly_safe(self):
        calls = []
        def handler(instruction, metadata, goal_state):
            calls.append(instruction)
            if len(calls) == 1:
                return ExecutionResult("failed", error="timeout", metadata={"transient": True})
            return ExecutionResult("ok", output="recovered")
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(max_attempts=2, idempotent=True, justification="read-only lookup has no external side effects")})
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, "recovered")
        self.assertEqual(result.metadata["attempts"], 2)
        self.assertEqual(len(calls), 2)

    def test_retry_delay_runs_only_between_retryable_attempts(self):
        calls, delays = [], []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            if len(calls) < 3:
                return ExecutionResult("failed", error="busy", metadata={"transient": True})
            return "recovered"
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(3, True, "read only", retry_delay_seconds=0.25)}, sleeper=delays.append)
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["attempts"], 3)
        self.assertEqual(delays, [0.25, 0.25])

    def test_retry_backoff_progresses_and_caps_each_wait(self):
        calls, delays = [], []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            if len(calls) < 5:
                return ExecutionResult("failed", error="busy", metadata={"transient": True})
            return "recovered"
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(5, True, "read only", retry_delay_seconds=10, retry_backoff_multiplier=2)}, sleeper=delays.append)
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.metadata["attempts"], 5)
        self.assertEqual(delays, [10.0, 20.0, 40.0, 60.0])

    def test_retry_jitter_is_bounded_and_injectable(self):
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
        self.assertEqual(delays, [5.0, 15.0])
        with self.assertRaises(ValueError):
            CapabilityRetryPolicy(2, True, "read only", retry_delay_seconds=1).delay_before_attempt(1, 1.1)

    def test_terminal_failure_never_sleeps(self):
        delays = []
        def handler(instruction, metadata, goal_state):
            return ExecutionResult("failed", error="bad input", metadata={"transient": False})
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(3, True, "read only", retry_delay_seconds=1)}, sleeper=delays.append)
        result = executor.execute(action(), state())
        self.assertEqual(result.metadata["attempts"], 1)
        self.assertEqual(delays, [])

    def test_unconfigured_capability_never_retries(self):
        calls = []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            return ExecutionResult("failed", error="timeout", metadata={"transient": True})
        result = ResilientCapabilityExecutor({"read": handler}).execute(action(), state())
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.metadata["attempts"], 1)
        self.assertEqual(len(calls), 1)

    def test_needs_approval_is_never_retried(self):
        calls = []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            return ExecutionResult("needs_approval", metadata={"transient": True})
        executor = ResilientCapabilityExecutor({"write": handler}, retry_policies={"write": CapabilityRetryPolicy(max_attempts=3, idempotent=True, justification="test fixture")})
        result = executor.execute(action("write"), state())
        self.assertEqual(result.status, "needs_approval")
        self.assertEqual(result.metadata["attempts"], 1)
        self.assertEqual(len(calls), 1)

    def test_non_transient_failure_is_terminal(self):
        calls = []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            return ExecutionResult("failed", error="invalid input", metadata={"transient": False})
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(2, True, "read only")})
        result = executor.execute(action(), state())
        self.assertEqual(result.metadata["attempts"], 1)
        self.assertEqual(len(calls), 1)

    def test_declared_retryable_exception_can_recover(self):
        calls = []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            if len(calls) == 1:
                raise TimeoutError("temporary provider timeout")
            return "recovered"
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(2, True, "read-only provider call", retryable_exceptions=(TimeoutError,))})
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, "recovered")
        self.assertEqual(result.metadata["attempts"], 2)
        self.assertEqual(len(calls), 2)

    def test_undeclared_exception_remains_terminal(self):
        calls = []
        def handler(instruction, metadata, goal_state):
            calls.append(1)
            raise ConnectionError("not declared retryable")
        executor = ResilientCapabilityExecutor({"read": handler}, retry_policies={"read": CapabilityRetryPolicy(3, True, "read-only provider call", retryable_exceptions=(TimeoutError,))})
        result = executor.execute(action(), state())
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.metadata["attempts"], 1)
        self.assertFalse(result.metadata["transient"])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
