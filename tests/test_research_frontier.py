from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fap_research_frontier import build_frontier, load_reviews


class ResearchFrontierTests(unittest.TestCase):
    def _rows(self):
        return [
            {
                "doi": "10.1/a",
                "title": "Atmospheric convection under changing boundary conditions",
                "journal": "J1",
                "published": "2026-09-20",
                "subjects": ["Atmospheric Science"],
                "abstract_available": True,
                "cited_by_count": 3,
                "update_flags": [],
                "unresolved_kinds": ["limitations", "validation", "scale", "future_test"],
                "resolved_kinds": ["question", "method", "outcome"],
                "open_question_hints": ["Future work should test whether the mechanism changes across spatial scales."],
                "limitation_hints": ["A limitation is the restricted domain."],
                "claim_hints": ["Results suggest convection changes under the tested forcing."],
                "url": "https://example.org/a",
            },
            {
                "doi": "10.1/b",
                "title": "Atmospheric convection and scale dependent forecast errors",
                "journal": "J2",
                "published": "2026-09-20",
                "subjects": ["Atmospheric Science"],
                "abstract_available": True,
                "cited_by_count": 1,
                "update_flags": ["relation"],
                "unresolved_kinds": ["uncertainty", "validation", "robustness", "scale"],
                "resolved_kinds": ["question", "method", "uncertainty"],
                "open_question_hints": ["It remains unclear which scale dominates the forecast error."],
                "limitation_hints": [],
                "claim_hints": [],
                "url": "https://example.org/b",
            },
            {
                "doi": "10.1/c",
                "title": "Atmospheric convection in a regional ensemble",
                "journal": "J1",
                "published": "2026-09-19",
                "subjects": ["Atmospheric Science"],
                "abstract_available": True,
                "cited_by_count": 0,
                "update_flags": [],
                "unresolved_kinds": ["generalization", "validation", "future_test"],
                "resolved_kinds": ["question", "design"],
                "open_question_hints": ["Further studies are needed in different regions."],
                "limitation_hints": [],
                "claim_hints": [],
                "url": "https://example.org/c",
            },
            {
                "doi": "10.1/d",
                "title": "Atmospheric convection observations and model validation",
                "journal": "J3",
                "published": "2026-09-18",
                "subjects": ["Atmospheric Science"],
                "abstract_available": True,
                "cited_by_count": 2,
                "update_flags": [],
                "unresolved_kinds": ["causality", "mechanism", "validation"],
                "resolved_kinds": ["question", "method", "data_provenance"],
                "open_question_hints": [],
                "limitation_hints": [],
                "claim_hints": [],
                "url": "https://example.org/d",
            },
        ]

    def test_clusters_unresolved_questions_into_frontier(self):
        frontier = build_frontier(self._rows(), max_clusters=20, min_papers=2)
        self.assertGreaterEqual(frontier["cluster_count"], 1)
        top = frontier["frontier"][0]
        self.assertEqual(top["topic"], "Atmospheric Science")
        self.assertEqual(top["paper_count"], 4)
        self.assertGreaterEqual(len(top["research_questions"]), 4)
        self.assertGreaterEqual(len(top["provisional_hypothesis_falsification_loops"]), 1)
        self.assertEqual(top["epistemic_status"], "research-frontier; not verified fact")

    def test_loader_accepts_compact_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "reviews.jsonl"
            path.write_text(
                "\n".join(json.dumps(x, ensure_ascii=False) for x in self._rows()) + "\n",
                encoding="utf-8",
            )
            rows = load_reviews(path)
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["doi"], "10.1/a")


if __name__ == "__main__":
    unittest.main()
