from __future__ import annotations

from pathlib import Path
import unittest

import fap_v87_78_conversation_fuzz_gateway as gateway
from fap_conversation_quality_fuzz import (
    generate_quality_cases,
    has_internal_error_marker,
    history_for,
    repeated_sentence_ratio,
)
from fap_reflective_conversation import ReflectiveConversationOrgan


ROOT = Path(__file__).resolve().parents[1]


class ConversationQualityFuzzTests(unittest.TestCase):
    def setUp(self):
        self.organ = ReflectiveConversationOrgan()

    def test_semantic_quality_properties(self):
        counts = {}
        for case in generate_quality_cases(seed=879001, rounds=64):
            counts[case.kind] = counts.get(case.kind, 0) + 1
            history = history_for(case.history_concept_id) if case.history_concept_id else []
            out = self.organ.run(case.prompt, history)

            if case.kind == "explicit_unknown_isolation":
                self.assertIsNone(
                    out,
                    f"explicit new subject borrowed history: {case}",
                )
                continue

            self.assertIsNotNone(out, case)
            self.assertEqual(out.get("topic_id"), case.expected_topic_id, case)
            reply = str(out.get("reply") or "")
            self.assertTrue(reply.strip(), case)
            self.assertFalse(has_internal_error_marker(reply), case)
            self.assertLess(repeated_sentence_ratio(reply), 0.35, case)
            self.assertLessEqual(len(reply), 5000, case)

            if case.kind == "subjectless_followup":
                self.assertTrue(out.get("followup_resolved"), case)

        self.assertEqual(set(counts), {
            "semantic_stability",
            "subjectless_followup",
            "explicit_unknown_isolation",
            "current_turn_override",
        })
        self.assertTrue(all(value >= 64 for value in counts.values()))

    def test_latest_gateway_does_not_context_hijack_explicit_unknown_subject(self):
        core = gateway.FAPV8778Unified()
        sid = "v8779-quality-context-isolation"
        path = gateway.base.MEMORY.path(sid)
        if path.exists():
            path.unlink()
        core.clear_route_continuity(sid)
        try:
            cases = [
                case
                for case in generate_quality_cases(seed=879002, rounds=24)
                if case.kind == "explicit_unknown_isolation"
            ]
            self.assertGreaterEqual(len(cases), 24)
            for index, case in enumerate(cases[:24]):
                history_topic = case.history_concept_id
                seed_prompt = history_for(history_topic)[0]["text"]
                first = core.chat(seed_prompt, sid)
                self.assertIn(first["verdict"], {"OK", "PARTIAL"})

                second = core.chat(case.prompt, sid)
                self.assertNotIn(
                    "context-followup",
                    second.get("route", []),
                    f"case {index}: {case.prompt}",
                )

                if path.exists():
                    path.unlink()
                core.clear_route_continuity(sid)
                gateway.base.MEMORY._cache.pop(gateway.base.safe_session(sid), None)
        finally:
            if path.exists():
                path.unlink()
            core.clear_route_continuity(sid)
            gateway.base.MEMORY._cache.pop(gateway.base.safe_session(sid), None)

    def test_latest_gateway_preserves_subjectless_followup(self):
        core = gateway.FAPV8778Unified()
        sid = "v8779-quality-followup"
        path = gateway.base.MEMORY.path(sid)
        if path.exists():
            path.unlink()
        core.clear_route_continuity(sid)
        try:
            cases = [
                case
                for case in generate_quality_cases(seed=879003, rounds=16)
                if case.kind == "subjectless_followup"
            ]
            for case in cases[:16]:
                seed_prompt = history_for(case.history_concept_id)[0]["text"]
                core.chat(seed_prompt, sid)
                follow = core.chat(case.prompt, sid)
                self.assertIn("context-followup", follow.get("route", []), case)

                if path.exists():
                    path.unlink()
                core.clear_route_continuity(sid)
                gateway.base.MEMORY._cache.pop(gateway.base.safe_session(sid), None)
        finally:
            if path.exists():
                path.unlink()
            core.clear_route_continuity(sid)
            gateway.base.MEMORY._cache.pop(gateway.base.safe_session(sid), None)


if __name__ == "__main__":
    unittest.main()
