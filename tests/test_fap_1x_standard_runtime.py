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
        self.assertEqual(result.endpoint_id, "factual_qa")
        self.assertIn("299,792,458", result.payload.get("reply", ""))

    def test_rule_reasoner_derives_polygon_angle_sum(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("四角形の内角の和は？")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "rule_reasoner")
        self.assertIn("360", result.payload.get("reply", ""))

    def test_rule_reasoner_resolves_subject_from_session_history(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        runtime.chat("四角形について", session_id="geometry")
        result = runtime.run_turn("内角の和は？", session_id="geometry")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "rule_reasoner")
        self.assertIn("360", result.payload.get("reply", ""))
        self.assertEqual(result.payload.get("context_source"), "conversation-context")

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

    def test_known_topic_can_be_narrated_from_local_knowledge(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("大気の運動について知っていることを教えて")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "knowledge_narrator")
        self.assertIn("気圧", result.payload.get("reply", ""))
        self.assertTrue(result.payload.get("grounded"))
        self.assertTrue(result.payload.get("knowledge_narrator"))

    def test_knowledge_inventory_is_exposed(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("FAPは何を知っている？")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "knowledge_narrator")
        inventory = result.payload.get("knowledge_inventory") or {}
        self.assertGreater(inventory.get("chunks", 0), 0)


    def test_response_intelligence_solves_verified_arithmetic_fallback(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("計算してください: (37+5)*3")
        self.assertEqual(result.state, "handled")
        self.assertEqual(result.endpoint_id, "response_series")
        self.assertIn("126", result.payload.get("reply", ""))
        execution = result.payload.get("response_series_execution") or {}
        self.assertTrue(execution.get("selection_changed_primary"))
        self.assertIn("arithmetic", execution.get("consensus_sources", []))

    def test_response_intelligence_solves_linear_equation_fallback(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("方程式 2x + 3 = 11 を解いて")
        self.assertEqual(result.state, "handled")
        self.assertIn("x = 4", result.payload.get("reply", ""))
        self.assertIn(
            "linear_equation",
            (result.payload.get("response_series_execution") or {}).get(
                "consensus_sources",
                [],
            ),
        )

    def test_response_intelligence_status_is_version_clean(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        status = runtime.status()
        intelligence = status.get("response_intelligence") or {}
        self.assertTrue(intelligence.get("enabled"))
        self.assertEqual(intelligence.get("max_lanes"), 128)
        self.assertEqual(intelligence.get("max_synthesis_width"), 16)
        specialists = intelligence.get("safe_specialists", [])
        self.assertGreaterEqual(len(specialists), 16)
        self.assertIn("subproblem", specialists)
        self.assertIn("linear_equation", specialists)
        self.assertIn("counterexample_search", specialists)
        self.assertEqual(
            intelligence.get("native_revision"),
            "1.0.01-cpp-native-r008",
        )

    def test_runtime_exposes_reasoning_episode(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("計算してください: (19+8)*4")
        episode = result.payload.get("reasoning_episode") or {}
        self.assertEqual(episode.get("contract"), "fap.reasoning.episode.v1")
        self.assertEqual(episode.get("verdict"), "OK")
        self.assertTrue(episode.get("false_success_guard"))
        self.assertTrue(episode.get("plan_execute_verify_repair_reverify"))
        self.assertGreaterEqual(episode.get("attempted_passes", 0), 1)

    def test_reasoning_status_reports_episode_contract(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        intelligence = runtime.status().get("response_intelligence") or {}
        self.assertEqual(
            intelligence.get("episode_contract"),
            "fap.reasoning.episode.v1",
        )
        self.assertEqual(intelligence.get("max_escalation_passes"), 3)

    def test_known_primary_fact_remains_primary_when_already_strong(self):
        runtime = FAP1xStandardRuntime(root=ROOT)
        result = runtime.run_turn("真空中の光速は？")
        self.assertEqual(result.endpoint_id, "factual_qa")
        execution = result.payload.get("response_series_execution") or {}
        self.assertEqual(execution.get("selected"), "primary")

if __name__ == "__main__":
    unittest.main()
