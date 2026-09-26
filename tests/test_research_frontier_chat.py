from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fap_research_frontier_chat import ResearchFrontierOrgan
from fap_v87_53_research_frontier_gateway import FAPV8753Unified


class ResearchFrontierChatTests(unittest.TestCase):
    def _snapshot(self):
        return {
            "generated_at": "2026-09-22T07:30:00+09:00",
            "papers_processed": 50000,
            "cluster_count": 120,
            "epistemic_status": "automated research-priority snapshot; not verified fact",
            "frontier": [
                {
                    "topic": "Atmospheric Science",
                    "priority_score": 3.2,
                    "paper_count": 400,
                    "abstract_count": 300,
                    "post_publication_update_records": 2,
                    "unresolved_appraisal_items": 2500,
                    "top_unresolved_kinds": [["validation", 300], ["scale", 280]],
                    "research_questions": [
                        {"kind": "validation", "supporting_papers": 300, "question": "Atmospheric Scienceの主要主張は独立データで再現するか？"},
                        {"kind": "scale", "supporting_papers": 280, "question": "Atmospheric Scienceはスケールで支配機構が変わるか？"},
                    ],
                    "provisional_hypothesis_falsification_loops": [
                        {
                            "hypothesis": "Atmospheric Scienceでは条件により支配機構が切り替わる可能性がある。",
                            "falsifier": "全条件で同一モデルが外部検証される。",
                            "next_test": "複数スケールで外部検証する。",
                        }
                    ],
                },
                {
                    "topic": "Genomics",
                    "priority_score": 2.7,
                    "paper_count": 250,
                    "abstract_count": 180,
                    "post_publication_update_records": 0,
                    "unresolved_appraisal_items": 1900,
                    "top_unresolved_kinds": [["causality", 220]],
                    "research_questions": [
                        {"kind": "causality", "supporting_papers": 220, "question": "Genomicsで相関と因果をどう分けるか？"}
                    ],
                    "provisional_hypothesis_falsification_loops": [],
                },
            ],
        }

    def test_frontier_organ_reads_snapshot_and_ranks_topic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "knowledge").mkdir()
            (root / "knowledge" / "research_frontier_latest.json").write_text(
                json.dumps(self._snapshot(), ensure_ascii=False),
                encoding="utf-8",
            )
            organ = ResearchFrontierOrgan(root)
            out = organ.run("大気について未解決問題は？", [])
            self.assertIsNotNone(out)
            self.assertTrue(out["research_frontier"])
            self.assertEqual(out["papers_processed"], 50000)
            self.assertEqual(out["selected_frontier"][0]["topic"], "Atmospheric Science")
            self.assertIn("反証条件", out["reply"])
            self.assertIn("断定", out["reply"])

    def test_non_frontier_prompt_does_not_hijack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "knowledge").mkdir()
            (root / "knowledge" / "research_frontier_latest.json").write_text(
                json.dumps(self._snapshot(), ensure_ascii=False),
                encoding="utf-8",
            )
            organ = ResearchFrontierOrgan(root)
            self.assertIsNone(organ.run("大気の運動を説明して", []))

    def test_v8753_reports_frontier_capability(self):
        core = FAPV8753Unified()
        caps = core.capabilities()
        self.assertIn("research-frontier-prioritization", caps)
        self.assertIn("frontier-to-falsification-loop", caps)


if __name__ == "__main__":
    unittest.main()
