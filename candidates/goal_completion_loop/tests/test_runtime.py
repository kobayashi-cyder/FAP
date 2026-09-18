from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop import AutonomousConversationRuntime


class AutonomousRuntimeTests(unittest.TestCase):
    def test_one_instruction_plans_executes_critiques_and_replans_to_completion(self):
        planner_calls = []
        critic_calls = []

        def planner(payload):
            planner_calls.append(payload)
            if payload["state"]["steps"] == 0:
                return {
                    "actions": [
                        {
                            "kind": "inspect",
                            "instruction": "inspect the current situation",
                            "expected_outcome": "situation understood",
                        }
                    ]
                }
            return {
                "actions": [
                    {
                        "kind": "apply",
                        "instruction": "apply the remaining change",
                        "expected_outcome": "goal complete",
                    }
                ]
            }

        def critic(payload):
            critic_calls.append(payload)
            if payload["action"]["kind"] == "inspect":
                return {
                    "satisfied": False,
                    "progress": 0.5,
                    "reason": "inspection complete",
                    "replan": True,
                    "next_hint": "apply the change",
                }
            return {
                "satisfied": True,
                "progress": 1.0,
                "reason": "all success criteria met",
                "criteria": {"finished": True},
            }

        handlers = {
            "inspect": lambda instruction, metadata, state: {"observed": True},
            "apply": lambda instruction, metadata, state: {"changed": True},
        }
        runtime = AutonomousConversationRuntime(
            planner_model=planner,
            critic_model=critic,
            handlers=handlers,
        )

        result = runtime.submit(
            "調べて、必要な変更をして、完了まで進めて",
            success_criteria=("必要な変更が完了",),
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.steps, 2)
        self.assertEqual(result.progress, 1.0)
        self.assertEqual(len(planner_calls), 2)
        self.assertEqual(len(critic_calls), 2)
        self.assertIn("changed", result.last_output)

    def test_unsupported_planner_capability_fails_closed(self):
        def planner(_payload):
            return {"actions": [{"kind": "unknown", "instruction": "do it"}]}

        def critic(_payload):
            return {"satisfied": True, "progress": 1.0, "reason": "done"}

        runtime = AutonomousConversationRuntime(
            planner_model=planner,
            critic_model=critic,
            handlers={"known": lambda instruction, metadata, state: "ok"},
        )
        result = runtime.submit("unsupported route")

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason, "planner_exception:ValueError")
        self.assertEqual(result.steps, 0)

    def test_approval_kind_pauses_then_resumes_from_checkpoint(self):
        calls = []

        def planner(_payload):
            return {
                "actions": [
                    {
                        "kind": "publish",
                        "instruction": "publish the prepared result",
                    }
                ]
            }

        def critic(_payload):
            return {"satisfied": True, "progress": 1.0, "reason": "published"}

        def publish(instruction, metadata, state):
            calls.append(instruction)
            return "published"

        with tempfile.TemporaryDirectory() as td:
            paused_runtime = AutonomousConversationRuntime(
                planner_model=planner,
                critic_model=critic,
                handlers={"publish": publish},
                approval_kinds={"publish"},
                state_dir=td,
            )
            paused = paused_runtime.submit("公開まで進める")
            self.assertEqual(paused.status, "paused")
            self.assertEqual(paused.reason, "approval_required")
            self.assertEqual(calls, [])

            resumed_runtime = AutonomousConversationRuntime(
                planner_model=planner,
                critic_model=critic,
                handlers={"publish": publish},
                approval_kinds={"publish"},
                approval=lambda action, state: True,
                state_dir=td,
            )
            done = resumed_runtime.submit("公開まで進める")
            self.assertEqual(done.status, "completed")
            self.assertEqual(calls, ["publish the prepared result"])

    def test_invalid_critic_response_blocks_instead_of_claiming_success(self):
        def planner(_payload):
            return {"actions": [{"kind": "inspect", "instruction": "inspect"}]}

        def critic(_payload):
            return {
                "satisfied": True,
                "progress": 2.0,
                "reason": "invalid confidence",
            }

        runtime = AutonomousConversationRuntime(
            planner_model=planner,
            critic_model=critic,
            handlers={"inspect": lambda instruction, metadata, state: "observed"},
        )
        result = runtime.submit("verify carefully")

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason, "critic_exception:ValueError")
        self.assertEqual(result.steps, 1)


if __name__ == "__main__":
    unittest.main()
