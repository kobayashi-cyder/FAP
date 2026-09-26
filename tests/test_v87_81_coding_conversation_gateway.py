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

    def test_response_series_redundancy_is_large_and_bounded(self) -> None:
        core = gateway.FAPV8781Unified()
        status = core.status()
        response = status.get("response_redundancy") or {}
        self.assertTrue(response.get("enabled"))
        self.assertEqual(response.get("max_lanes"), 64)
        self.assertEqual(response.get("max_synthesis_width"), 8)
        self.assertTrue(response.get("partial_coverage_allowed"))
        self.assertEqual(response.get("native_parity_revision"), "1.0.01-cpp-native-r003")

        simple = core._pre_response_plan("説明して", [])
        complex_plan = core.response_redundancy.plan(
            ("複数観点で検証し、反例と代替案と制約も検討してください。" * 10),
            uncertainty=0.95,
            confidence=0.25,
            disagreement=True,
            counterexample=True,
            route_candidates=8,
            verification_depth=6,
            retries=4,
            intent_count=4,
        )
        self.assertGreater(complex_plan.active_lanes, simple["active_lanes"])
        self.assertGreaterEqual(complex_plan.active_lanes, 48)


if __name__ == "__main__":
    unittest.main()
