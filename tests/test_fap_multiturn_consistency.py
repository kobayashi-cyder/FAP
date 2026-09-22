from __future__ import annotations

import inspect
import unittest

from fap_discourse_context import is_transparent_discourse_turn
from fap_multiturn_consistency_fuzz import generate_multiturn_cases
import fap_reflective_conversation as reflective_module
from fap_reflective_conversation import ReflectiveConversationOrgan


class MultiTurnConsistencyFuzzTests(unittest.TestCase):
    def setUp(self):
        self.organ = ReflectiveConversationOrgan()

    def test_transparent_discourse_is_data_driven(self):
        for text in ("ありがとう", "なるほど", "了解", "OK"):
            self.assertTrue(is_transparent_discourse_turn(text), text)
        for text in ("qxunknownsubject", "未知主題とは？", "波"):
            self.assertFalse(is_transparent_discourse_turn(text), text)

        source = inspect.getsource(reflective_module)
        self.assertNotIn("ありがとう", source)
        self.assertNotIn("なるほど", source)

    def test_multiturn_topic_resolution_properties(self):
        counts = {}
        for case in generate_multiturn_cases(seed=8780001, rounds=64):
            counts[case.kind] = counts.get(case.kind, 0) + 1
            out = self.organ.run(case.prompt, list(case.history))

            if not case.expect_resolved:
                self.assertIsNone(
                    out,
                    f"stale topic resurrected across newer explicit subject: {case}",
                )
                continue

            self.assertIsNotNone(out, case)
            self.assertTrue(out.get("followup_resolved"), case)
            self.assertEqual(out.get("topic_id"), case.expected_topic_id, case)

        self.assertEqual(
            set(counts),
            {
                "latest_known_wins",
                "unknown_subject_blocks_stale_resurrection",
                "explicit_correction_switch",
                "correction_persists_to_followup",
                "acknowledgement_keeps_topic",
            },
        )
        self.assertTrue(all(value >= 64 for value in counts.values()))


if __name__ == "__main__":
    unittest.main()
