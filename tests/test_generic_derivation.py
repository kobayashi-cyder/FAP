from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import fap_generic_derivation as derivation_module
from fap_generic_derivation import GenericDerivationEngine
from fap_v87_57_generic_derivation_gateway import FAPV8757Unified


class GenericDerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.engine = GenericDerivationEngine(cls.root)

    def test_pythagorean_derivation_is_generated_and_verified(self):
        out = self.engine.run("三平方の定理を導出して", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["ok"])
        self.assertTrue(out["derivation_verified"])
        self.assertIn("a^2 + b^2 = c^2", out["reply"])
        self.assertIn("algebraic-entailment", out["route_tags"])
        self.assertIn("independent-countercheck", out["route_tags"])
        self.assertNotIn("確定回答できません", out["reply"])

    def test_same_engine_combines_multiple_premises(self):
        out = self.engine.run("対称差の式を証明して", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["derivation_verified"])
        self.assertEqual(out["derivation_coefficients"], ["1", "1"])
        self.assertIn("2*p = s + d", out["reply"])

    def test_same_engine_rearranges_equations(self):
        out = self.engine.run("中点公式を導出して", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["derivation_verified"])
        self.assertIn("m = (x1+x2)/2", out["reply"])

    def test_unknown_proof_does_not_fabricate(self):
        out = self.engine.run("フェルマーの最終定理を証明して", [])
        self.assertIsNone(out)

    def test_engine_has_no_pythagorean_name_branch(self):
        source = inspect.getsource(derivation_module)
        for forbidden in ("三平方", "ピタゴラス", "Pythagorean", "pythagorean"):
            self.assertNotIn(forbidden, source)

    def test_latest_chat_routes_derivation_end_to_end(self):
        core = FAPV8757Unified()
        out = core.chat("三平方の定理を導出して", "v8757-pythagorean-e2e")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("derivation-retrieve", out["route"])
        self.assertIn("symbolic-normalize", out["route"])
        self.assertIn("algebraic-entailment", out["route"])
        self.assertIn("independent-countercheck", out["route"])
        self.assertTrue(out["derivation"]["enabled"])
        self.assertTrue(out["derivation"]["verified"])
        self.assertEqual(out["derivation"]["id"], "math.right_triangle.area_rearrangement")
        self.assertNotIn("確定回答できません", out["reply"])


if __name__ == "__main__":
    unittest.main()
