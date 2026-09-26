from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import fap_generic_rule_reasoner as rule_module
from fap_generic_rule_reasoner import GenericRuleReasoner
from fap_v87_58_generic_rule_gateway import FAPV8758Unified


class GenericRuleReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.reasoner = GenericRuleReasoner(cls.root)

    def test_short_followup_resolves_subject_from_conversation(self):
        history = [
            {"role": "user", "text": "三平方の定理を導出して"},
            {"role": "assistant", "text": "直角三角形の直角辺を a,b、斜辺を c とします。"},
        ]
        out = self.reasoner.run("内角の和は？", history)
        self.assertIsNotNone(out)
        self.assertTrue(out["rule_verified"])
        self.assertEqual(out["context_source"], "conversation-context")
        self.assertEqual(out["subject_id"], "euclidean_triangle")
        self.assertEqual(out["relation_id"], "interior_angle_sum_degrees")
        self.assertEqual(out["value"], 180.0)
        self.assertIn("180°", out["reply"])

    def test_same_rules_apply_to_another_entity_without_code_branch(self):
        out = self.reasoner.run("四角形の内角の和は？", [])
        self.assertIsNotNone(out)
        self.assertTrue(out["rule_verified"])
        self.assertEqual(out["value"], 360.0)
        ids = out["evidence_ids"]
        self.assertIn("polygon_vertex_triangulation", ids)
        self.assertIn("polygon_interior_sum_from_triangulation", ids)

    def test_rule_chain_is_recursive_not_exact_answer_lookup(self):
        out = self.reasoner.run("三角形の内角の和を教えて", [])
        self.assertIsNotNone(out)
        trace = out["rule_trace"]
        rules = [x["id"] for x in trace if x.get("kind") == "rule"]
        self.assertEqual(
            rules,
            ["polygon_vertex_triangulation", "polygon_interior_sum_from_triangulation"],
        )

    def test_unknown_relation_falls_through(self):
        self.assertIsNone(self.reasoner.run("三角形の未知量fooは？", []))

    def test_engine_source_contains_no_specific_answer_or_theorem_handler(self):
        source = inspect.getsource(rule_module)
        for forbidden in ("内角の和", "三角形", "四角形", "180°", "360°"):
            self.assertNotIn(forbidden, source)

    def test_latest_chat_reproduces_screenshot_followup_end_to_end(self):
        core = FAPV8758Unified()
        sid = "v8758-context-angle-followup"
        first = core.chat("三平方の定理を導出して", sid)
        self.assertEqual(first["verdict"], "OK")
        second = core.chat("内角の和は？", sid)
        self.assertEqual(second["verdict"], "OK")
        self.assertIn("180°", second["reply"])
        self.assertIn("context-subject-resolve", second["route"])
        self.assertIn("recursive-rule-chain", second["route"])
        self.assertTrue(second["rule_reasoning"]["enabled"])
        self.assertTrue(second["rule_reasoning"]["verified"])
        self.assertEqual(second["rule_reasoning"]["context_source"], "conversation-context")
        self.assertNotIn("確定回答できません", second["reply"])


if __name__ == "__main__":
    unittest.main()
