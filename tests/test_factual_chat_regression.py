from __future__ import annotations

import unittest

import fap_v87_10_program_synth_gateway as base
from fap_factual_qa import FactualQAOrgan
from fap_v78_distilled import DistilledFAPOrgan
from fap_v87_12_semantic_adaptive_gateway import FAPV8712
from fap_v87_42_science_capability_gateway import FAPV8742Unified
from fap_reflective_conversation import ReflectiveConversationOrgan
from fap_v87_43_reflective_chat_gateway import FAPV8743Unified


class FactualChatRegressionTests(unittest.TestCase):
    def test_vacuum_light_speed_is_answered_directly(self):
        out = FactualQAOrgan().run("真空中の光速度は？")
        self.assertIsNotNone(out)
        self.assertTrue(out["factual_qa"])
        self.assertIn("299,792,458", out["reply"])
        self.assertEqual(out["fact_id"], "vacuum_speed_of_light")

    def test_light_speed_does_not_activate_constraint_circuit(self):
        active = DistilledFAPOrgan().activate("真空中の光速度は？")
        self.assertNotIn("constraint_aware", [x.name for x in active])

    def test_real_chat_routes_fact_before_distilled_procedure(self):
        core = FAPV8712()
        out = core.chat("真空中の光速度は？", "v8740-factual-light-speed")
        self.assertIn("299,792,458", out["reply"])
        self.assertEqual(out["verdict"], "OK")
        self.assertNotIn("制約を先に固定", out["reply"])

    def test_actual_performance_constraint_still_activates(self):
        active = DistilledFAPOrgan().activate("応答速度を100ms以内にする制約で高速化したい")
        self.assertIn("constraint_aware", [x.name for x in active])

    def test_factual_verifier_reports_direct_answer(self):
        organ = FactualQAOrgan()
        result = organ.run("プランク定数の値は？")
        verdict, note = base.VerificationOrgan().verify(
            base.Intent("chat", 0.9, [("chat", 0.9)]),
            result,
        )
        self.assertEqual(verdict, "OK")
        self.assertIn("直接回答", note)


    def test_latency_feedback_is_conversational(self):
        result = DistilledFAPOrgan().run("20秒程度応答にかかりました。", [])
        self.assertTrue(result["ok"])
        self.assertFalse(result["needs_teacher"])
        self.assertIn("応答遅延", result["reply"])
        self.assertNotIn("確定回答できません", result["reply"])

    def test_chat_status_is_lightweight_shape(self):
        st = base.FAPV8710().chat_status()
        self.assertEqual(st["state"], "ready")
        self.assertIn("version", st)
        self.assertNotIn("teacher_available", st)


    def test_science_capability_question_is_answered(self):
        core = FAPV8742Unified()
        out = core.chat("科学的な質問に答えられますか？", "v8742-science-capability")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("科学的な質問に答えられます", out["reply"])
        self.assertIn("物理定数", out["reply"])
        self.assertIn("self-capability", out["route"])
        self.assertGreaterEqual(out["confidence"], 0.95)

    def test_unresolved_chat_is_not_verified_ok(self):
        result = {
            "ok": True,
            "reply": "その内容は現在の蒸留回路だけでは確定回答できません。",
            "needs_teacher": True,
        }
        verdict, note = base.VerificationOrgan().verify(
            base.Intent("chat", 0.6, [("chat", 0.6)]),
            result,
        )
        self.assertEqual(verdict, "PARTIAL")
        self.assertIn("確定回答", note)


    def test_atmospheric_motion_is_explained_reflectively(self):
        core = FAPV8743Unified()
        out = core.chat("大気の運動に関しては？", "v8743-atmosphere")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("気圧傾度力", out["reply"])
        self.assertIn("コリオリ", out["reply"])
        self.assertIn("reflective-chat", out["route"])
        self.assertGreaterEqual(out["confidence"], 0.9)

    def test_reflective_followup_resolves_recent_topic(self):
        organ = ReflectiveConversationOrgan()
        history = [
            {"role": "user", "text": "大気の運動に関しては？"},
            {"role": "assistant", "text": "大気の運動は気圧差などで決まります。"},
        ]
        out = organ.run("それは？", history)
        self.assertIsNotNone(out)
        self.assertTrue(out["followup_resolved"])
        self.assertEqual(out["topic_id"], "atmospheric_motion")

    def test_reflective_compare_uses_two_grounded_concepts(self):
        out = ReflectiveConversationOrgan().run("気圧傾度力とコリオリ効果の違いを比較して", [])
        self.assertIsNotNone(out)
        self.assertEqual(out["reasoning_mode"], "compare")
        self.assertGreaterEqual(len(out["evidence_ids"]), 2)
        self.assertIn("違いを短く言うと", out["reply"])


if __name__ == "__main__":
    unittest.main()
