import unittest

from fap_goal_loop.goal_loop import ExecutionResult
from fap_goal_loop.resilient_capability import CapabilityRetryPolicy
from fap_goal_loop.resilient_runtime import ResilientAutonomousConversationRuntime


class ResilientRuntimeTests(unittest.TestCase):
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

    def test_transient_idempotent_capability_recovers_inside_runtime(self):
        calls = {"n": 0}

        def read(_instruction, _metadata, _state):
            calls["n"] += 1
            if calls["n"] == 1:
                return ExecutionResult("failed", error="timeout", metadata={"transient": True})
            return "payload"

        runtime = ResilientAutonomousConversationRuntime(
            planner_model=self.planner,
            critic_model=self.critic,
            handlers={"read": read},
            retry_policies={
                "read": CapabilityRetryPolicy(
                    max_attempts=2,
                    idempotent=True,
                    justification="read-only operation",
                )
            },
        )
        result = runtime.submit("fetch data", success_criteria=["completed"], max_steps=2)
        self.assertEqual("succeeded", result.status)
        self.assertEqual(2, calls["n"])
        self.assertEqual(2, result.state.history[-1].result.metadata["attempts"])

    def test_default_runtime_policy_does_not_replay(self):
        calls = {"n": 0}

        def write(_instruction, _metadata, _state):
            calls["n"] += 1
            return ExecutionResult("failed", error="timeout", metadata={"transient": True})

        runtime = ResilientAutonomousConversationRuntime(
            planner_model=self.planner,
            critic_model=self.critic,
            handlers={"read": write},
        )
        runtime.submit("write data", success_criteria=["completed"], max_steps=1)
        self.assertEqual(1, calls["n"])

    def test_unknown_retry_policy_fails_closed_at_construction(self):
        with self.assertRaises(ValueError):
            ResilientAutonomousConversationRuntime(
                planner_model=self.planner,
                critic_model=self.critic,
                handlers={"read": lambda *_args: "ok"},
                retry_policies={"missing": CapabilityRetryPolicy()},
            )


if __name__ == "__main__":
    unittest.main()
