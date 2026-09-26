from __future__ import annotations

from pathlib import Path
import unittest

from fap_knowledge_narrator import KnowledgeNarrator


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeNarratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.narrator = KnowledgeNarrator(ROOT)

    def test_can_explain_known_repository_knowledge(self):
        out = self.narrator.run("大気の運動について知っていることを教えて")
        self.assertIsNotNone(out)
        self.assertTrue(out["ok"])
        self.assertTrue(out["grounded"])
        self.assertTrue(out["knowledge_narrator"])
        self.assertIn("気圧", out["reply"])
        self.assertTrue(out["evidence_ids"])

    def test_inventory_reports_known_topics(self):
        out = self.narrator.run("FAPは何を知っている？")
        self.assertIsNotNone(out)
        inv = out["knowledge_inventory"]
        self.assertGreater(inv["chunks"], 0)
        self.assertTrue(inv["titles"])
        self.assertIn("FAPのローカル知識", out["reply"])

    def test_current_request_marks_dated_knowledge_for_refresh(self):
        out = self.narrator.run("現在のAI気象予測について知っていることを教えて")
        self.assertIsNotNone(out)
        self.assertTrue(out["needs_teacher"])
        self.assertIn("更新確認", out["reply"])
        self.assertTrue(
            any(x["live_required"] for x in out["knowledge_sources"])
        )

    def test_opaque_unknown_is_not_narrated(self):
        out = self.narrator.run("ZXQV-UNKNOWN-7F9A31について知っていることを教えて")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
