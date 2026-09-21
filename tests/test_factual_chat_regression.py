from __future__ import annotations

import unittest

import fap_v87_10_program_synth_gateway as base
from fap_factual_qa import FactualQAOrgan
from fap_v78_distilled import DistilledFAPOrgan
from fap_v87_12_semantic_adaptive_gateway import FAPV8712


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


if __name__ == "__main__":
    unittest.main()
