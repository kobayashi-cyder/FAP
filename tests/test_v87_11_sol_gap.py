from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fap_v87_10_program_synth_gateway as base
from fap_sol_gap_controller import DeliberationEngine, MultiIntentPlanner, PersistentGoalState
from fap_v87_11_sol_gap_gateway import FAPV8711


class V8711SolGapTests(unittest.TestCase):
    def test_multi_intent_detects_datetime_and_calculator(self):
        found = MultiIntentPlanner().detect("今日の日付と12+34を教えて")
        self.assertEqual([x.name for x in found], ["datetime", "calculator"])

    def test_multi_intent_chat_executes_both(self):
        core = FAPV8711()
        out = core.chat("今日の日付と12+34を教えて", "v8711-multi")
        self.assertEqual(out["ability"], "multi")
        self.assertIn("日時:", out["reply"])
        self.assertIn("12+34 = 46", out["reply"])
        self.assertEqual(len(out["tool_calls"]), 2)

    def test_goal_and_constraints_persist(self):
        with tempfile.TemporaryDirectory() as td:
            store = PersistentGoalState(Path(td))
            store.update("a", "6×6の盤面でゲームを作って。星を5個集めたら勝ち。Qwenは使わないで。")
            s = store.load("a")
            self.assertTrue(s["open_goal"])
            joined = " ".join(s["constraints"])
            self.assertIn("6×6", joined)
            self.assertTrue("5個" in joined or "5" in joined)
            self.assertIn("Qwen", joined)

    def test_goal_survives_many_raw_turns(self):
        core = FAPV8711()
        sid = "v8711-long"
        core.chat("目的は単一HTMLのゲームを完成させること。Qwenは使わない。", sid)
        for i in range(35):
            core.chat(f"雑談メモ{i}", sid)
        out = core.chat("今の目的と条件は？", sid)
        self.assertEqual(out["ability"], "memory")
        self.assertIn("単一HTML", out["reply"])
        self.assertIn("Qwen", out["reply"])
        self.assertIn("単一HTML", out["goal_state"]["open_goal"])
        self.assertNotIn("今の目的と条件", out["goal_state"]["open_goal"])

    def test_deliberation_prefers_planning_for_goal_completion(self):
        core = FAPV8711()
        state = {"open_goal": "目的を達成する", "constraints": []}
        p = DeliberationEngine(core.distilled).plan(
            "途中で失敗しても目的を達成するまで進める", [], state
        )
        self.assertEqual(p["selected"], "planning")

    def test_unknown_fact_is_not_fabricated(self):
        core = FAPV8711()
        out = core.chat("架空惑星ゼルパの2026年人口は？", "v8711-unknown")
        self.assertIn("確定回答できません", out["reply"])
        self.assertTrue(out["coverage"]["unknown_boundary"])

    def test_codegen_v8710_is_preserved(self):
        core = FAPV8711()
        out = core.chat("Pythonで文章から数字だけ抽出して合計を出すコードを作って", "v8711-code")
        self.assertEqual(out["ability"], "builder")
        self.assertTrue(out["artifacts"])
        self.assertEqual(out["verdict"], "OK")

    def test_vague_followup_inherits_retained_goal(self):
        core = FAPV8711()
        sid = "v8711-followup"
        core.chat("目的はエラーが出ても完成まで実装を進めること。RAM制約を守る。", sid)
        out = core.chat("では続きはどうする？", sid)
        self.assertIn(out["deliberation"]["selected"], {"planning", "context_followup", "constraint_aware"})
        self.assertNotIn("確定回答できません", out["reply"])
        self.assertTrue(out["goal_state"]["open_goal"])

    def test_status_exposes_reasoning_controller(self):
        st = FAPV8711().status()
        self.assertEqual(st["version"], "87.11-sol-gap")
        self.assertTrue(st["reasoning_controller"]["multi_intent"])
        self.assertEqual(st["reasoning_controller"]["raw_history_turns"], 160)


if __name__ == "__main__":
    unittest.main()
