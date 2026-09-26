from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_goal_loop import (
    ConversationGoalRunner,
    Critique,
    ExecutionResult,
    GoalCompletionLoop,
    GoalSpec,
    GoalState,
    JSONGoalStateStore,
    PlannedAction,
)


class AdaptivePlanner:
    def plan(self, goal, state, hint=""):
        if state.steps == 0:
            return [PlannedAction("inspect", "inspect", "inspect current state", "state understood")]
        return [PlannedAction("finish", "act", "apply the remaining change", "goal satisfied")]


class AdaptiveExecutor:
    def execute(self, action, state):
        if action.action_id == "inspect":
            return ExecutionResult("ok", output={"observed": True})
        return ExecutionResult("ok", output={"done": True})


class AdaptiveCritic:
    def evaluate(self, goal, state, action, result):
        if action.action_id == "inspect":
            return Critique(
                satisfied=False,
                progress=0.45,
                reason="state understood",
                replan=True,
                next_hint="apply the remaining change",
            )
        return Critique(
            satisfied=True,
            progress=1.0,
            reason="success criteria satisfied",
            criteria={"done": True},
        )


class GoalCompletionLoopTests(unittest.TestCase):
    def test_runs_until_success_without_another_user_turn(self):
        loop = GoalCompletionLoop(AdaptivePlanner(), AdaptiveExecutor(), AdaptiveCritic())
        goal = GoalSpec(
            goal_id="g-complete",
            objective="finish the task",
            success_criteria=("done",),
        )
        state = loop.run(goal)

        self.assertEqual(state.status, "completed")
        self.assertEqual(state.steps, 2)
        self.assertEqual(state.progress, 1.0)
        self.assertEqual([x.action.action_id for x in state.history], ["inspect", "finish"])

    def test_failure_triggers_replan_and_recovers(self):
        class Planner:
            def plan(self, goal, state, hint=""):
                action = "fallback" if state.failures else "primary"
                return [PlannedAction(action, "tool", action)]

        class Executor:
            def execute(self, action, state):
                if action.action_id == "primary":
                    return ExecutionResult("failed", error="primary failed")
                return ExecutionResult("ok", output="recovered")

        class Critic:
            def evaluate(self, goal, state, action, result):
                if result.status == "failed":
                    return Critique(False, 0.1, "retry another route", retryable=True, replan=True)
                return Critique(True, 1.0, "fallback satisfied objective")

        loop = GoalCompletionLoop(Planner(), Executor(), Critic())
        state = loop.run(GoalSpec("g-retry", "recover automatically"))

        self.assertEqual(state.status, "completed")
        self.assertEqual(state.failures, 1)
        self.assertEqual(state.steps, 2)
        self.assertEqual(state.history[-1].action.action_id, "fallback")

    def test_stops_when_there_is_no_progress(self):
        class Planner:
            def plan(self, goal, state, hint=""):
                return [PlannedAction(f"a-{state.replans}", "think", f"attempt {state.replans}")]

        class Executor:
            def execute(self, action, state):
                return ExecutionResult("ok", output="unchanged")

        class Critic:
            def evaluate(self, goal, state, action, result):
                return Critique(False, 0.0, "no measurable progress", replan=True)

        loop = GoalCompletionLoop(Planner(), Executor(), Critic())
        goal = GoalSpec(
            "g-stall",
            "do not loop forever",
            max_no_progress=2,
            max_same_action=10,
            max_steps=10,
        )
        state = loop.run(goal)

        self.assertEqual(state.status, "stalled")
        self.assertEqual(state.reason, "no_progress_limit_reached")
        self.assertEqual(state.steps, 2)

    def test_repeated_identical_action_is_bounded(self):
        class Planner:
            def plan(self, goal, state, hint=""):
                return [PlannedAction("same", "think", "repeat me")]

        class Executor:
            def execute(self, action, state):
                return ExecutionResult("ok")

        class Critic:
            def evaluate(self, goal, state, action, result):
                return Critique(False, min(0.9, state.steps * 0.1), "keep trying", replan=True)

        loop = GoalCompletionLoop(Planner(), Executor(), Critic())
        goal = GoalSpec(
            "g-repeat",
            "bound repeated actions",
            max_same_action=2,
            max_no_progress=10,
            max_steps=10,
        )
        state = loop.run(goal)

        self.assertEqual(state.status, "stalled")
        self.assertEqual(state.reason, "repeated_action_limit_reached")
        self.assertEqual(state.steps, 2)

    def test_approval_required_action_pauses_and_can_resume(self):
        calls = []

        class Planner:
            def plan(self, goal, state, hint=""):
                return [PlannedAction("external", "external", "perform external change", requires_approval=True)]

        class Executor:
            def execute(self, action, state):
                calls.append(action.action_id)
                return ExecutionResult("ok")

        class Critic:
            def evaluate(self, goal, state, action, result):
                return Critique(True, 1.0, "done")

        with tempfile.TemporaryDirectory() as td:
            store = JSONGoalStateStore(td)
            goal = GoalSpec("g-approval", "external action")
            paused_loop = GoalCompletionLoop(Planner(), Executor(), Critic(), store=store)
            paused = paused_loop.run(goal)

            self.assertEqual(paused.status, "paused")
            self.assertEqual(paused.reason, "approval_required")
            self.assertEqual(calls, [])
            self.assertEqual(paused.steps, 0)

            approved_loop = GoalCompletionLoop(
                Planner(),
                Executor(),
                Critic(),
                store=store,
                approval=lambda action, state: True,
            )
            completed = approved_loop.run(goal)

            self.assertEqual(completed.status, "completed")
            self.assertEqual(calls, ["external"])
            self.assertEqual(completed.steps, 1)

    def test_checkpoint_round_trip_and_terminal_resume(self):
        with tempfile.TemporaryDirectory() as td:
            store = JSONGoalStateStore(td)
            goal = GoalSpec("g-store", "persist state")
            original = GoalState(goal=goal, progress=0.5, steps=1, replans=1)
            store.save(original)
            loaded = store.load("g-store")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.goal, goal)
            self.assertEqual(loaded.progress, 0.5)
            self.assertEqual(loaded.steps, 1)

            loop = GoalCompletionLoop(AdaptivePlanner(), AdaptiveExecutor(), AdaptiveCritic(), store=store)
            completed = loop.run(goal)
            self.assertEqual(completed.status, "completed")
            self.assertGreaterEqual(completed.steps, 2)

            resumed = loop.run(goal)
            self.assertEqual(resumed.status, "completed")
            self.assertEqual(resumed.steps, completed.steps)

    def test_conversation_adapter_turns_instruction_into_goal(self):
        loop = GoalCompletionLoop(AdaptivePlanner(), AdaptiveExecutor(), AdaptiveCritic())
        runner = ConversationGoalRunner(loop)
        state = runner.submit("この仕事を最後まで終わらせて", success_criteria=("完了",))

        self.assertEqual(state.status, "completed")
        self.assertTrue(state.goal.goal_id.startswith("goal-"))
        self.assertEqual(state.goal.objective, "この仕事を最後まで終わらせて")


if __name__ == "__main__":
    unittest.main()
