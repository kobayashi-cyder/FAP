from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fap_inquiry_engine import InquiryEngine
from fap_sol_gap_controller import PersistentGoalState
from fap_v87_60_relevance_isolation_gateway import FAPV8760Unified


class RelevanceIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_unrelated_unknown_query_does_not_borrow_history_topic(self):
        engine = InquiryEngine(self.root)
        history = [
            {"role": "user", "text": "大気の運動について説明して"},
            {"role": "assistant", "text": "気圧傾度力、コリオリ効果、重力などが関係します。"},
        ]
        out = engine.run("zxqvblorfという語の意味を教えてください", history)
        self.assertIsNone(out)

    def test_directly_grounded_query_still_uses_inquiry(self):
        engine = InquiryEngine(self.root)
        out = engine.run("大気の運動について教えてください", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["inquiry_reasoning"])
        self.assertGreater(out["resolved_questions"], 0)

    def test_polite_one_shot_request_is_not_persistent_goal(self):
        with tempfile.TemporaryDirectory() as td:
            store = PersistentGoalState(Path(td))
            state = store.update("s", "ある用語の意味を教えてください。")
            self.assertEqual(state["open_goal"], "")

    def test_durable_work_request_can_be_persistent_goal(self):
        with tempfile.TemporaryDirectory() as td:
            store = PersistentGoalState(Path(td))
            state = store.update("s", "この推論器を改善して完成させてください。")
            self.assertIn("改善", state["open_goal"])

    def test_unrelated_unknown_turn_does_not_become_previous_science_answer_end_to_end(self):
        core = FAPV8760Unified()
        sid = "v8760-relevance-e2e"
        first = core.chat("大気の運動について説明して", sid)
        self.assertIn(first["verdict"], {"OK", "PARTIAL"})
        second = core.chat("zxqvblorfという語の意味を教えてください", sid)
        self.assertEqual(second["verdict"], "PARTIAL")
        self.assertNotIn("エントロピー", second["reply"])
        self.assertNotIn("コリオリ", second["reply"])
        self.assertNotIn("私はFAPです", second["reply"])


if __name__ == "__main__":
    unittest.main()
