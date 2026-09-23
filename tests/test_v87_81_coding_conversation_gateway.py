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


if __name__ == "__main__":
    unittest.main()
