from __future__ import annotations

import unittest

import fap_v87_10_program_synth_gateway as base
from fap_factual_qa import FactualQAOrgan
from fap_v78_distilled import DistilledFAPOrgan
from fap_v87_12_semantic_adaptive_gateway import FAPV8712
from fap_v87_42_science_capability_gateway import FAPV8742Unified
from fap_reflective_conversation import ReflectiveConversationOrgan
from fap_v87_43_reflective_chat_gateway import FAPV8743Unified
from fap_v87_44_context_followup_gateway import FAPV8744Unified
from fap_inquiry_engine import InquiryEngine
from fap_v87_45_inquiry_loop_gateway import FAPV8745Unified
from fap_v87_46_mass_inquiry_gateway import FAPV8746Unified
from fap_v87_47_mass_inquiry_burst_gateway import FAPV8747Unified


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


    def test_latest_fast_status_reports_descendant_version(self):
        import fap_v87_43_reflective_chat_gateway as v43
        st = v43.Handler._fast_status()
        self.assertEqual(st["version"], "87.43-unified-chat")
        self.assertEqual(st["mainline_version"], "87.43")


    def test_open_ended_premise_is_discussed_without_fake_facts(self):
        organ = ReflectiveConversationOrgan()
        out = organ.run("仮に物理を情報圧縮として捉えると、何が欠損する？", [])
        self.assertIsNotNone(out)
        self.assertEqual(out["reasoning_mode"], "premise")
        self.assertEqual(out["grounding"], "user-premise")
        self.assertIn("検証可能な議論", out["reply"])
        self.assertNotIn("確定回答できません", out["reply"])

    def test_short_opinion_followup_uses_previous_user_premise(self):
        organ = ReflectiveConversationOrgan()
        history = [
            {"role": "user", "text": "複雑な現象を圧縮して扱うという見方は有効だと思う。"},
            {"role": "assistant", "text": "仮説として整理できます。"},
        ]
        out = organ.run("それはどう思う？", history)
        self.assertIsNotNone(out)
        self.assertTrue(out["followup_resolved"])
        self.assertIn("複雑な現象を圧縮", out["reply"])


    def test_natural_clarification_followup_uses_recent_atmosphere_topic(self):
        core = FAPV8744Unified()
        sid = "v8744-natural-followup"
        first = core.chat("大気の運動について", sid)
        self.assertEqual(first["verdict"], "OK")
        out = core.chat("どういうことなのかわかりますか？", sid)
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("要するに", out["reply"])
        self.assertIn("気圧", out["reply"])
        self.assertIn("reflective-chat", out["route"])
        self.assertIn("clarify", out["route"])
        self.assertIn("context-followup", out["route"])
        self.assertNotIn("確定回答できません", out["reply"])

    def test_understanding_question_resolves_recent_known_topic(self):
        organ = ReflectiveConversationOrgan()
        history = [
            {"role": "user", "text": "大気の運動について"},
            {"role": "assistant", "text": "大気の運動は気圧傾度力などで決まります。"},
        ]
        out = organ.run("これが何を意味するかわかりますか？", history)
        self.assertIsNotNone(out)
        self.assertTrue(out["followup_resolved"])
        self.assertTrue(out["contextual_followup"])
        self.assertEqual(out["reasoning_mode"], "clarify")


    def test_generic_inquiry_generates_and_resolves_questions(self):
        engine = InquiryEngine(base.ROOT)
        out = engine.run("大気の運動について疑問点はありますか？", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["inquiry_reasoning"])
        self.assertTrue(out["audit_mode"])
        self.assertGreaterEqual(out["generated_questions"], 96)
        self.assertGreaterEqual(out["resolved_questions"], 8)
        self.assertIn("Q:", out["reply"])
        self.assertIn("解消:", out["reply"])

    def test_inquiry_route_is_visible_in_latest_chat(self):
        core = FAPV8745Unified()
        out = core.chat("大気の運動について疑問点はありますか？", "v8745-inquiry-route")
        self.assertIn("question-generate", out["route"])
        self.assertIn("question-resolve", out["route"])
        self.assertNotIn("確定回答できません", out["reply"])

    def test_followup_topic_can_be_retrieved_from_data_not_router_branch(self):
        core = FAPV8745Unified()
        sid = "v8745-data-followup"
        core.chat("大気の運動について", sid)
        out = core.chat("では、台風の進路予測は？", sid)
        self.assertIn("inquiry-retrieve", out["route"])
        self.assertTrue("台風" in out["reply"] or "指向流" in out["reply"])
        self.assertNotIn("現在の蒸留回路だけでは確定回答できません", out["reply"])

    def test_current_forecast_keeps_live_data_boundary(self):
        core = FAPV8745Unified()
        out = core.chat("現在の台風3号の進路は？", "v8745-live-boundary")
        self.assertEqual(out["verdict"], "PARTIAL")
        self.assertIn("最新データ", out["critic"])


    def test_mass_inquiry_default_is_high_volume(self):
        core = FAPV8746Unified()
        out = core.chat("大気の運動について疑問点を出して", "v8746-mass-default")
        self.assertIn("question-generate", out["route"])
        self.assertGreaterEqual(out["inquiry"]["generated"], 96)
        self.assertGreater(out["inquiry"]["resolved"], 0)

    def test_mass_inquiry_explicit_count_can_reach_128(self):
        engine = InquiryEngine(base.ROOT)
        out = engine.run("大気の運動について128問、問い出しと問い潰しをして", [])
        self.assertIsNotNone(out)
        self.assertGreaterEqual(out["generated_questions"], 128)
        self.assertEqual(out["target_questions"], 128)

    def test_mass_inquiry_keeps_unknowns_explicit(self):
        engine = InquiryEngine(base.ROOT)
        out = engine.run("大気の運動について疑問点を大量に出して", [])
        self.assertIsNotNone(out)
        self.assertEqual(
            out["generated_questions"],
            out["resolved_questions"] + out["unresolved_questions"],
        )
        self.assertIn("resolution_rate", out)


    def test_mass_inquiry_default_is_256(self):
        core = FAPV8747Unified()
        out = core.chat("大気の運動について疑問点を出して", "v8747-default-256")
        self.assertGreaterEqual(out["inquiry"]["generated"], 256)

    def test_mass_inquiry_burst_phrase_requests_2048(self):
        engine = InquiryEngine(base.ROOT)
        out = engine.run("大気の運動について問い出しと問い潰しをとにかく増やして", [])
        self.assertIsNotNone(out)
        self.assertEqual(out["target_questions"], 2048)
        self.assertGreaterEqual(out["generated_questions"], 2048)


if __name__ == "__main__":
    unittest.main()
