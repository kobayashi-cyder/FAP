from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop.goal_loop import ExecutionResult
from fap_goal_loop.resilient import ResilientCapabilityHandler, RetryPolicy


class DummyState:
    pass


class ResilientCapabilityHandlerTests(unittest.TestCase):
    def test_transient_failure_then_success(self):
        calls = []
        def handler(instruction, metadata, state):
            calls.append(instruction)
            if len(calls) == 1:
                return ExecutionResult("failed", error="timeout")
            return ExecutionResult("ok", output="done")
        result = ResilientCapabilityHandler(handler)("work", {}, DummyState())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, "done")
        self.assertEqual(result.metadata["attempts"], 2)

    def test_non_transient_failure_not_retried(self):
        calls = []
        def handler(instruction, metadata, state):
            calls.append(1)
            return ExecutionResult("failed", error="invalid_request")
        result = ResilientCapabilityHandler(handler)("work", {}, DummyState())
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(calls), 1)

    def test_approval_is_never_retried(self):
        calls = []
        def handler(instruction, metadata, state):
            calls.append(1)
            return ExecutionResult("needs_approval", error="approval_required")
        result = ResilientCapabilityHandler(handler)("work", {}, DummyState())
        self.assertEqual(result.status, "needs_approval")
        self.assertEqual(len(calls), 1)

    def test_retry_is_bounded(self):
        calls = []
        def handler(instruction, metadata, state):
            calls.append(1)
            return ExecutionResult("failed", error="temporarily_unavailable")
        wrapped = ResilientCapabilityHandler(handler, policy=RetryPolicy(max_attempts=3))
        result = wrapped("work", {}, DummyState())
        self.assertEqual(len(calls), 3)
        self.assertTrue(result.metadata["retry_exhausted"])

    def test_policy_rejects_unbounded_configuration(self):
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=6)


if __name__ == "__main__":
    unittest.main()
