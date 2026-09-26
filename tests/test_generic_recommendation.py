from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import fap_generic_recommendation as recommendation_module
from fap_generic_recommendation import GenericRecommendationEngine
from fap_v87_61_generic_recommendation_gateway import FAPV8761Unified


class GenericRecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.engine = GenericRecommendationEngine(cls.root)

    def test_lunch_request_returns_ranked_candidates(self):
        out = self.engine.run("昼ご飯は何がおすすめですか？", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["recommendation_verified"])
        self.assertEqual(out["domain_id"], "meal")
        self.assertEqual(out["context_id"], "lunch")
        self.assertGreaterEqual(len(out["candidate_ids"]), 3)
        self.assertNotIn("確定回答できません", out["reply"])

    def test_constraint_followup_uses_recent_recommendation_context(self):
        history = [
            {"role": "user", "text": "昼ご飯は何がおすすめですか？"},
            {"role": "assistant", "text": "候補を考えます。"},
        ]
        out = self.engine.run("アレルギーは無いです。", history)
        self.assertIsNotNone(out)
        self.assertTrue(out["contextual_followup"])
        self.assertIn("アレルギー指定なし", out["signal_labels"])
        self.assertGreaterEqual(len(out["candidate_ids"]), 3)

    def test_followup_without_recommendation_context_is_not_hijacked(self):
        history = [
            {"role": "user", "text": "三平方の定理を導出して"},
            {"role": "assistant", "text": "a^2+b^2=c^2"},
        ]
        self.assertIsNone(self.engine.run("アレルギーは無いです。", history))

    def test_preferences_rerank_same_candidate_pool(self):
        light = self.engine.run("昼食は軽めでおすすめを教えて", [])
        filling = self.engine.run("昼食はがっつり系でおすすめを教えて", [])
        self.assertIsNotNone(light)
        self.assertIsNotNone(filling)
        self.assertNotEqual(light["candidate_ids"][0], filling["candidate_ids"][0])

    def test_python_has_no_specific_prompt_answer_branch(self):
        source = inspect.getsource(recommendation_module)
        self.assertNotIn("昼ご飯は何がおすすめですか", source)
        self.assertNotIn("アレルギーは無いです", source)

    def test_latest_chat_reproduces_screenshot_flow_end_to_end(self):
        core = FAPV8761Unified()
        sid = "v8761-lunch-followup"
        first = core.chat("昼ご飯は何がおすすめですか？", sid)
        self.assertEqual(first["verdict"], "OK")
        self.assertIn("recommendation-intent", first["route"])
        self.assertTrue(first["recommendation"]["enabled"])
        self.assertGreaterEqual(len(first["recommendation"]["candidate_ids"]), 3)

        second = core.chat("アレルギーは無いです。", sid)
        self.assertEqual(second["verdict"], "OK")
        self.assertTrue(second["recommendation"]["contextual_followup"])
        self.assertIn("conversation-constraint-compose", second["route"])
        self.assertNotIn("確定回答できません", second["reply"])


if __name__ == "__main__":
    unittest.main()
