from __future__ import annotations

import unittest

from fap_goal_loop.capability_policy import CapabilityRegistration, build_capability_handlers
from fap_goal_loop.goal_loop import ExecutionResult, GoalSpec, GoalState


def _state() -> GoalState:
    return GoalState(goal=GoalSpec(goal_id="g", objective="test"))


class CapabilityPolicyTests(unittest.TestCase):
    def test_retry_safe_requires_idempotency_basis(self):
        with self.assertRaises(ValueError):
            CapabilityRegistration("fetch", lambda *_: "ok", retry_safe=True)

    def test_unsafe_handler_is_never_retried(self):
        calls = {"n": 0}
        def handler(*_):
            calls["n"] += 1
            return ExecutionResult("failed", error="timeout")
        result = build_capability_handlers([CapabilityRegistration("write", handler)])["write"]("x", {}, _state())
        self.assertEqual(result.status, "failed")
        self.assertEqual(calls["n"], 1)

    def test_retry_safe_handler_recovers_from_transient_failure(self):
        calls = {"n": 0}
        def handler(*_):
            calls["n"] += 1
            if calls["n"] == 1:
                return ExecutionResult("failed", error="timeout")
            return ExecutionResult("ok", output="done")
        handlers = build_capability_handlers([CapabilityRegistration("fetch", handler, retry_safe=True, idempotency_basis="read-only request", max_attempts=2)])
        result = handlers["fetch"]("x", {}, _state())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, "done")
        self.assertEqual(result.metadata["attempts"], 2)

    def test_approval_is_never_retried(self):
        calls = {"n": 0}
        def handler(*_):
            calls["n"] += 1
            return ExecutionResult("needs_approval", error="timeout")
        handlers = build_capability_handlers([CapabilityRegistration("fetch", handler, retry_safe=True, idempotency_basis="read-only request", max_attempts=3)])
        result = handlers["fetch"]("x", {}, _state())
        self.assertEqual(result.status, "needs_approval")
        self.assertEqual(calls["n"], 1)

    def test_duplicate_names_are_rejected(self):
        reg = CapabilityRegistration("fetch", lambda *_: "ok")
        with self.assertRaises(ValueError):
            build_capability_handlers([reg, reg])


if __name__ == "__main__":
    unittest.main()
