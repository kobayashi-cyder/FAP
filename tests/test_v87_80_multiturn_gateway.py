from __future__ import annotations

import json
import unittest

import fap_v87_80_multiturn_consistency_gateway as gateway
from fap_conversation_quality_fuzz import history_for
from fap_reflective_conversation import CONCEPTS


class V8780MultiTurnGatewayTests(unittest.TestCase):
    def setUp(self):
        self.core = gateway.FAPV8780Unified()

    def _reset(self, sid: str) -> None:
        path = gateway.base.MEMORY.path(sid)
        if path.exists():
            path.unlink()
        gateway.base.MEMORY._cache.pop(gateway.base.safe_session(sid), None)
        self.core.clear_route_continuity(sid)

    def _append_exchange(self, sid: str, user: str, assistant: str) -> None:
        gateway.base.MEMORY.append_exchange(
            sid,
            user,
            assistant,
            {"intent": "chat"},
            {"intent": "chat", "verdict": "OK"},
        )

    def test_unknown_new_subject_blocks_older_topic_end_to_end(self):
        sid = "v8780-stale-topic-block"
        self._reset(sid)
        try:
            old = CONCEPTS[0]
            old_history = history_for(old.concept_id)
            self._append_exchange(sid, old_history[0]["text"], old_history[1]["text"])
            self._append_exchange(
                sid,
                "qznovelunknownsubjectvxとはどういう意味？",
                "その語についてローカル根拠がありません。",
            )

            out = self.core.chat("それってどういう意味？", sid)
            self.assertNotIn("context-followup", out.get("route", []))
            self.assertNotIn(old.summary[:20], str(out.get("reply", "")))
            json.dumps(out, ensure_ascii=False, allow_nan=False)
        finally:
            self._reset(sid)

    def test_correction_topic_persists_to_followup_end_to_end(self):
        sid = "v8780-correction-followup"
        self._reset(sid)
        try:
            old = next(c for c in CONCEPTS if c.concept_id == "convection")
            new = next(c for c in CONCEPTS if c.concept_id == "wave")
            old_history = history_for(old.concept_id)
            self._append_exchange(sid, old_history[0]["text"], old_history[1]["text"])
            self._append_exchange(
                sid,
                "自然対流ではなく波について説明して",
                new.summary,
            )

            out = self.core.chat("その点をもう少し", sid)
            self.assertIn("context-followup", out.get("route", []))
            self.assertIn(new.summary[:12], str(out.get("reply", "")))
            self.assertNotIn(old.summary[:12], str(out.get("reply", "")))
            json.dumps(out, ensure_ascii=False, allow_nan=False)
        finally:
            self._reset(sid)

    def test_status_reports_multiturn_hardening_without_fca_dependency(self):
        status = self.core.status()
        self.assertEqual(status.get("version"), "87.80-unified-chat")
        hardening = status.get("multiturn_consistency_hardening") or {}
        self.assertTrue(hardening.get("enabled"))
        self.assertTrue(hardening.get("new_unknown_subject_blocks_stale_topic"))
        self.assertTrue(hardening.get("explicit_correction_asserted_side_priority"))
        self.assertFalse(hardening.get("utterance_specific_topic_branches_added"))
        self.assertFalse(hardening.get("fca_required"))


if __name__ == "__main__":
    unittest.main()
