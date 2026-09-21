from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fap_epistemic_learning import EpistemicLedger, QuestionValueScorer
from fap_inquiry_engine import InquiryEngine, InquiryQuestion
from fap_scientific_modeling import ScientificModelComposer
from fap_v87_49_scientific_modeling_gateway import FAPV8749Unified
from fap_v87_50_recent_science_gateway import FAPV8750Unified


class EpistemicLearningTests(unittest.TestCase):
    def test_question_value_prefers_falsification_over_redundant_definition(self):
        scorer = QuestionValueScorer()
        q1 = InquiryQuestion("q1", "definition", "対象Xとは何か？")
        q2 = InquiryQuestion("q2", "definition", "対象Xの定義は何か？")
        q3 = InquiryQuestion("q3", "falsify", "対象Xの説明を反証するには何を観測すべきか？")
        ranked = scorer.rank([q1, q2, q3], 0.8)
        self.assertEqual(ranked[0].kind, "falsify")
        self.assertGreater(q3.value_score, q2.value_score)

    def test_verified_learning_persists_and_recalls(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = EpistemicLedger(Path(td))
            out = ledger.promote(
                topic="試験対象",
                kind="mechanism",
                question="試験対象はどう働くか？",
                answer="試験対象は入力Aによって状態Bへ変化する。",
                evidence_ids=["source-a"],
                value_score=0.91,
                confidence=0.94,
            )
            self.assertEqual(out["status"], "promoted")

            reopened = EpistemicLedger(Path(td))
            recalled = reopened.recall("試験対象はどう働くの？")
            self.assertIsNotNone(recalled)
            self.assertIn("状態B", recalled["answer"])
            self.assertEqual(recalled["evidence_ids"], ["source-a"])

    def test_conflicting_conclusion_is_quarantined(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = EpistemicLedger(Path(td))
            first = ledger.promote(
                topic="現象X",
                kind="prediction",
                question="現象Xでは量Yは増加するか？",
                answer="現象Xでは量Yは増加する。",
                evidence_ids=["source-a"],
                value_score=0.93,
                confidence=0.95,
            )
            self.assertEqual(first["status"], "promoted")

            second = ledger.promote(
                topic="現象X",
                kind="prediction",
                question="現象Xでは量Yは増加するか？",
                answer="現象Xでは量Yは増加しない。",
                evidence_ids=["source-b"],
                value_score=0.95,
                confidence=0.95,
            )
            self.assertEqual(second["status"], "conflict")
            stats = ledger.stats()
            self.assertEqual(stats["entries"], 1)
            self.assertEqual(stats["conflicts"], 1)

    def test_unresolved_frontier_survives_new_instance(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = EpistemicLedger(Path(td))
            q = InquiryQuestion(
                "u1",
                "uncertainty",
                "対象Zの最大の未解決点は何か？",
                value_score=0.92,
            )
            ledger.update_frontier("対象Z", [q])
            reopened = EpistemicLedger(Path(td))
            rows = reopened.frontier_for("対象Z")
            self.assertTrue(rows)
            self.assertIn("未解決点", rows[0]["question"])

    def test_inquiry_learns_without_topic_specific_router(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            knowledge = root / "knowledge"
            knowledge.mkdir(parents=True)
            row = {
                "id": "generic-system",
                "title": "汎用系",
                "domain": "test",
                "text": (
                    "汎用系は入力差によって状態が変化する。"
                    "状態変化は結合条件に依存する。"
                    "観測誤差があるため予測には不確実性が残る。"
                    "検証には入力と出力を繰り返し測定する必要がある。"
                ),
            }
            (knowledge / "seed.jsonl").write_text(
                json.dumps(row, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            engine = InquiryEngine(root)
            engine.default_target = 32
            engine.resolve_budget = 32
            engine.max_rounds = 2
            out = engine.run("汎用系について疑問点を出して", [])
            self.assertIsNotNone(out)
            self.assertTrue(out["question_value_ranking"])
            self.assertTrue(out["persistent_epistemic_learning"])
            self.assertGreater(out["resolved_questions"], 0)
            self.assertGreaterEqual(out["epistemic_learning"]["ledger"]["entries"], 1)


    def test_atmospheric_dynamics_uses_structured_scientific_model(self):
        core = FAPV8749Unified()
        out = core.chat("大気の動き方を式も含めて解説して", "v8749-atmosphere-model")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("scientific-model", out["route"])
        self.assertEqual(out["scientific_model"]["model_id"], "atmospheric_dynamics")
        self.assertIn("質量保存", out["reply"])
        self.assertTrue(out["scientific_model"]["equations"])

    def test_model_composer_is_data_driven(self):
        composer = ScientificModelComposer(Path("."))
        out = composer.run("流体の運動を解説して", [])
        self.assertIsNotNone(out)
        self.assertEqual(out["model_id"], "generic_fluid_dynamics")
        self.assertTrue(out["model_equations"])
        self.assertGreater(out["model_match_score"], 0.1)


    def test_recent_science_is_attached_with_provenance(self):
        core = FAPV8750Unified()
        out = core.chat("大気の動き方を最新の科学見地も含めて解説して", "v8750-recent-science")
        self.assertEqual(out["verdict"], "OK")
        self.assertIn("scientific-model", out["route"])
        recent = out["scientific_model"]["recent_science"]
        self.assertTrue(recent)
        self.assertTrue(any(x["as_of"].startswith("2026-") for x in recent))
        self.assertTrue(all(x["source_url"].startswith("https://") for x in recent))
        self.assertIn("最新の取得済み科学見地", out["reply"])

    def test_science_snapshot_has_current_2026_evidence(self):
        core = FAPV8750Unified()
        updates = core.scientific_model.recent_science.updates
        self.assertGreaterEqual(len(updates), 6)
        self.assertTrue(any(u.as_of == "2026-05-12" and u.institution == "ECMWF" for u in updates))
        self.assertTrue(any(u.institution == "WMO" for u in updates))


if __name__ == "__main__":
    unittest.main()
