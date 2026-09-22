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
from fap_reflective_conversation import (
    CONCEPTS,
    ReflectiveConversationOrgan,
    is_context_only_followup,
)


ROOT = Path(__file__).resolve().parents[1]


class ConversationQualityFuzzTests(unittest.TestCase):
    def setUp(self):
        self.organ = ReflectiveConversationOrgan()

    @staticmethod
    def _reset_session(core, sid: str) -> None:
        path = gateway.base.MEMORY.path(sid)
        if path.exists():
            path.unlink()
        gateway.base.MEMORY._cache.pop(gateway.base.safe_session(sid), None)
        core.clear_route_continuity(sid)

    @classmethod
    def _seed_session(cls, core, sid: str, concept_id: str) -> None:
        cls._reset_session(core, sid)
        rows = history_for(concept_id)
        gateway.base.MEMORY.append_exchange(
            sid,
            rows[0]["text"],
            rows[1]["text"],
            {"intent": "chat"},
            {"intent": "chat", "verdict": "OK"},
        )

    def test_context_reference_classifier_is_subject_sensitive(self):
        for text in (
            "どういうこと？",
            "つまり？",
            "それってどういう意味？",
            "その点をもう一度説明して",
        ):
            self.assertTrue(is_context_only_followup(text), text)

        for text in (
            "qxunknownzvってどういうこと？",
            "qxunknownzvについて簡単に説明して",
            "qxunknownzvとはどういう意味？",
        ):
            self.assertFalse(is_context_only_followup(text), text)

        for concept in CONCEPTS:
            out = self.organ.run("どういうこと？", history_for(concept.concept_id))
            self.assertIsNotNone(out, concept.concept_id)
            self.assertEqual(out.get("topic_id"), concept.concept_id)

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
        self._reset_session(core, sid)
        try:
            cases = [
                case
                for case in generate_quality_cases(seed=879002, rounds=24)
                if case.kind == "explicit_unknown_isolation"
            ]
            self.assertGreaterEqual(len(cases), 24)
            for index, case in enumerate(cases[:24]):
                history_topic = case.history_concept_id
                self._seed_session(core, sid, history_topic)
                second = core.chat(case.prompt, sid)
                self.assertNotIn(
                    "context-followup",
                    second.get("route", []),
                    f"case {index}: {case.prompt}",
                )

                self._reset_session(core, sid)
        finally:
            self._reset_session(core, sid)

    def test_latest_gateway_preserves_subjectless_followup(self):
        core = gateway.FAPV8778Unified()
        sid = "v8779-quality-followup"
        path = gateway.base.MEMORY.path(sid)
        self._reset_session(core, sid)
        try:
            cases = [
                case
                for case in generate_quality_cases(seed=879003, rounds=16)
                if case.kind == "subjectless_followup"
            ]
            for case in cases[:16]:
                self._seed_session(core, sid, case.history_concept_id)
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
