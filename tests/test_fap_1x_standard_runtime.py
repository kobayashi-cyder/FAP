from __future__ import annotations

from pathlib import Path
import unittest

from fap_1x_standard_runtime import FAP1xStandardRuntime


ROOT = Path(__file__).resolve().parents[1]


class FAP1xStandardRuntimeTests(unittest.TestCase):
    def test_known_fact_uses_local_factual_endpoint(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("真空中の光速は？")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "general_reasoning_core")
        self.assertEqual(result.payload.get("reasoning_source"), "local_fact")
        self.assertIn("299,792,458", result.payload.get("reply", ""))

    def test_rule_reasoner_derives_polygon_angle_sum(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("四角形の内角の和は？")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "general_reasoning_core")
        self.assertEqual(result.payload.get("reasoning_source"), "rule_verified")
        self.assertIn("360", result.payload.get("reply", ""))

    def test_rule_reasoner_resolves_subject_from_session_history(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        runtime.chat("四角形について", session_id="geometry")
        result = runtime.run_turn("内角の和は？", session_id="geometry")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "general_reasoning_core")
        self.assertEqual(result.payload.get("reasoning_source"), "rule_verified")
        self.assertIn("360", result.payload.get("reply", ""))
        self.assertEqual(result.payload.get("selected_payload", {}).get("context_source"), "conversation-context")

    def test_reflective_reasoning_uses_user_premise_without_external_fact(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("もし観測誤差が原因だとしたら、どう考える？")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "reflective")
        self.assertTrue(result.payload.get("grounded"))
        self.assertEqual(result.payload.get("grounding"), "user-premise")

    def test_unknown_question_fails_closed(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("ZXQV-938271について断定して")
        self.assertEqual(result.state, "unhandled")
        self.assertEqual(runtime.chat("ZXQV-938271について断定して"), "")

    def test_status_reports_loaded_reasoning_graph(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        status = runtime.status()
        self.assertGreater(status["generic_rule_reasoner"]["entities"], 0)
        self.assertGreater(status["generic_rule_reasoner"]["relations"], 0)
        self.assertGreater(status["generic_rule_reasoner"]["rules"], 0)


if __name__ == "__main__":
    unittest.main()
