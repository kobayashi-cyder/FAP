from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fap_research_cycle import build_cycles, _query_variants
from fap_research_cycle_chat import ResearchCycleOrgan
from fap_v87_55_recursive_research_gateway import FAPV8755Unified


class ResearchCycleTests(unittest.TestCase):
    def _frontier(self):
        return {
            "papers_processed": 50000,
            "cluster_count": 2,
            "frontier": [
                {
                    "topic": "Atmospheric Science",
                    "priority_score": 3.5,
                    "paper_count": 420,
                    "abstract_count": 330,
                    "post_publication_update_records": 2,
                    "top_unresolved_kinds": [["validation", 300], ["scale", 250]],
                    "research_questions": [
                        {
                            "kind": "validation",
                            "supporting_papers": 300,
                            "question": "Atmospheric Scienceの主要主張は独立データで再現するか？",
                        }
                    ],
                    "provisional_hypothesis_falsification_loops": [
                        {
                            "hypothesis": "Atmospheric Scienceでは条件によって支配機構が切り替わる可能性がある。",
                            "falsifier": "全条件で同一モデルが標本外でも成立する。",
                            "next_test": "複数環境で外部検証する。",
                        }
                    ],
                    "example_papers": [
                        {"doi": "10.1234/a", "title": "A", "url": "https://example.org/a"}
                    ],
                },
                {
                    "topic": "Genomics",
                    "priority_score": 2.8,
                    "paper_count": 280,
                    "abstract_count": 200,
                    "post_publication_update_records": 0,
                    "top_unresolved_kinds": [["causality", 200]],
                    "research_questions": [
                        {
                            "kind": "causality",
                            "supporting_papers": 200,
                            "question": "Genomicsで相関と因果を分けるには何が必要か？",
                        }
                    ],
                    "provisional_hypothesis_falsification_loops": [],
                    "example_papers": [],
                },
            ],
        }

    def test_builds_falsifiable_cycles(self):
        out = build_cycles(self._frontier(), 10)
        self.assertEqual(out["cycle_count"], 2)
        first = out["cycles"][0]
        self.assertEqual(first["topic"], "Atmospheric Science")
        self.assertGreater(first["value_of_information"], 0)
        self.assertGreaterEqual(len(first["hypotheses"]), 3)
        for h in first["hypotheses"]:
            self.assertTrue(h["statement"])
            self.assertTrue(h["falsifier"])
            self.assertTrue(h["next_test"])
        self.assertEqual(first["phase"], "evidence-needed")
        self.assertEqual(first["source_dois"], ["10.1234/a"])

    def test_chat_reads_cycle_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "knowledge").mkdir()
            program = build_cycles(self._frontier(), 10)
            (root / "knowledge" / "research_cycle_latest.json").write_text(
                json.dumps(program, ensure_ascii=False),
                encoding="utf-8",
            )
            organ = ResearchCycleOrgan(root)
            out = organ.run("大気について次の検証を進めて", [])
            self.assertIsNotNone(out)
            self.assertTrue(out["research_cycle"])
            self.assertEqual(out["selected_cycles"][0]["topic"], "Atmospheric Science")
            self.assertIn("反証", out["reply"])
            self.assertIn("実証ではありません", out["reply"])

    def test_query_refinement_is_generic_by_question_kind(self):
        queries = _query_variants("Atmospheric Science", "validation", 3)
        self.assertEqual(queries[0], "Atmospheric Science")
        self.assertEqual(len(queries), 3)
        self.assertTrue(any("external validation" in q for q in queries[1:]))

    def test_cycle_has_recursive_search_fields(self):
        out = build_cycles(self._frontier(), 10)
        evidence = out["cycles"][0]["targeted_evidence"]
        self.assertIn("rounds", evidence)
        self.assertIn("saturation_ratio", evidence)
        self.assertIn("stop_reason", evidence)

    def test_plain_science_explanation_is_not_hijacked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "knowledge").mkdir()
            program = build_cycles(self._frontier(), 10)
            (root / "knowledge" / "research_cycle_latest.json").write_text(
                json.dumps(program, ensure_ascii=False),
                encoding="utf-8",
            )
            organ = ResearchCycleOrgan(root)
            self.assertIsNone(organ.run("大気の運動を説明して", []))


    def test_v8755_exposes_recursive_research_capabilities(self):
        core = FAPV8755Unified()
        caps = core.capabilities()
        self.assertIn("recursive-literature-rechallenge", caps)
        self.assertIn("search-saturation-stop", caps)
        status = core.status()
        self.assertEqual(status["version"], "87.55-unified-chat")
        self.assertTrue(status["recursive_research"]["enabled"])


if __name__ == "__main__":
    unittest.main()
