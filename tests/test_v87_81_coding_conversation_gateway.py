from __future__ import annotations

import json
import unittest

import fap_v87_81_coding_conversation_gateway as gateway


class V8781CodingConversationGatewayTests(unittest.TestCase):
    def test_status_exposes_consolidated_coding_continuity(self) -> None:
        core = gateway.FAPV8781Unified()
        status = core.status()
        self.assertEqual(status.get("version"), "87.81-unified-chat")
        self.assertEqual(status.get("mainline_version"), "87.81")
        coding = status.get("coding_conversation") or {}
        self.assertTrue(coding.get("structured_multi_edit"))
        self.assertTrue(coding.get("mixed_operation_planning"))
        self.assertTrue(coding.get("repository_session_continuity"))
        self.assertFalse(coding.get("repository_session_stores_source_text"))
        self.assertFalse(coding.get("fca_required"))
        json.dumps(status, ensure_ascii=False, allow_nan=False)

    def test_v8780_conversation_hardening_remains_enabled(self) -> None:
        status = gateway.FAPV8781Unified().status()
        hardening = status.get("multiturn_consistency_hardening") or {}
        self.assertTrue(hardening.get("enabled"))
        self.assertTrue(hardening.get("new_unknown_subject_blocks_stale_topic"))
        self.assertTrue(hardening.get("explicit_correction_asserted_side_priority"))

    def test_response_series_redundancy_executes_not_just_plans(self) -> None:
        core = gateway.FAPV8781Unified()
        status = core.status()
        response = status.get("response_redundancy") or {}
        self.assertTrue(response.get("enabled"))
        self.assertEqual(response.get("max_lanes"), 128)
        self.assertEqual(response.get("max_synthesis_width"), 16)
        self.assertTrue(response.get("lane_votes_execute"))
        self.assertTrue(response.get("verified_specialist_can_replace_weak_primary"))
        self.assertFalse(response.get("side_effecting_specialists_redundantly_executed"))
        self.assertEqual(response.get("native_parity_revision"), "1.0.01-cpp-native-r005")
        self.assertIn("factual", response.get("safe_specialists", []))
        self.assertIn("derivation", response.get("safe_specialists", []))

    def test_response_series_can_improve_actual_route_result(self) -> None:
        core = gateway.FAPV8781Unified()
        text = "真空中の光速は何ですか？"
        intent = core.intent.classify(text)
        result = core.route(intent, text, [])
        execution = result.get("response_series_execution") or {}
        self.assertEqual(execution.get("executed_lane_votes"), (result.get("response_redundancy") or {}).get("active_lanes"))
        self.assertFalse(execution.get("side_effecting_specialists_executed"))
        self.assertIn("299,792,458", result.get("reply", ""))


if __name__ == "__main__":
    unittest.main()
