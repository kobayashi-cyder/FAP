import unittest
from unittest.mock import patch

import fap_v87_03_distilled_gateway as g
from fap_v78_distilled import DistilledFAPOrgan


class V8703DistilledTests(unittest.TestCase):
    def test_local_status_is_ready_without_teacher(self):
        with patch.object(g.E2BOrgan, "available", return_value=False), patch.object(g.ImageOrgan, "available", return_value=(False, "off")):
            core = g.FAPV8703()
            s = core.status()
            self.assertEqual(s["state"], "ready")
            self.assertEqual(s["model"], "distilled:v78")
            self.assertFalse(s["teacher_available"])
            self.assertTrue(s["local_brain"])

    def test_greeting_is_local(self):
        r = DistilledFAPOrgan().run("こんにちは", [])
        self.assertTrue(r["ok"])
        self.assertTrue(r["local"])
        self.assertFalse(r["needs_teacher"])
        self.assertIn("FAP", r["reply"])

    def test_debugging_circuit_activates(self):
        r = DistilledFAPOrgan().run("エラーが出て動かない。切り分けて", [])
        self.assertIn("debugging", r["active_circuits"])
        self.assertIn("最小再現", r["reply"])

    def test_planning_circuit_activates(self):
        r = DistilledFAPOrgan().run("終わるまで自分で考えて進める計画", [])
        self.assertIn("planning", r["active_circuits"])
        self.assertIn("目標", r["reply"])

    def test_unknown_does_not_fabricate(self):
        r = DistilledFAPOrgan().run("XYZ123の事実を答えて", [])
        self.assertTrue(r["ok"])
        self.assertTrue(r["needs_teacher"])
        self.assertIn("確定回答できません", r["reply"])

    def test_calculator_regression(self):
        self.assertEqual(g.CalculatorOrgan().run("12+34はいくら？")["reply"], "12+34 = 46")


if __name__ == "__main__":
    unittest.main()
