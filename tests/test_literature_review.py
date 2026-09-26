from __future__ import annotations

import unittest

from fap_literature_review import CriticalAppraiser


class LiteratureReviewTests(unittest.TestCase):
    def test_abstract_appraisal_generates_many_questions(self):
        item = {
            "DOI": "10.1234/example.2026.1",
            "title": ["A prospective observational study of atmospheric forecast skill"],
            "container-title": ["Example Journal"],
            "publisher": "Example Publisher",
            "type": "journal-article",
            "published": {"date-parts": [[2026, 9, 20]]},
            "indexed": {"date-time": "2026-09-21T00:00:00Z"},
            "author": [{"family": "A"}, {"family": "B"}],
            "reference": [{"DOI": "10.1/a"}, {"DOI": "10.1/b"}],
            "is-referenced-by-count": 2,
            "abstract": (
                "<jats:p>We evaluate a model using an independent test set. "
                "The analysis reports uncertainty, sensitivity analysis, limitations, "
                "and data from satellite observations. Future work should test "
                "generalization under extreme conditions.</jats:p>"
            ),
        }
        out = CriticalAppraiser().review(item)
        self.assertGreaterEqual(out.generated_questions, 30)
        self.assertGreater(out.resolved_questions, 5)
        self.assertGreater(out.unresolved_questions, 0)
        self.assertTrue(out.abstract_available)
        self.assertEqual(out.doi, "10.1234/example.2026.1")

    def test_missing_abstract_stays_unresolved_instead_of_inventing(self):
        item = {
            "DOI": "10.1234/noabstract",
            "title": ["Minimal paper metadata"],
            "container-title": ["Example Journal"],
            "type": "journal-article",
            "published": {"date-parts": [[2026, 9, 20]]},
        }
        out = CriticalAppraiser().review(item)
        self.assertFalse(out.abstract_available)
        self.assertGreater(out.unresolved_questions, out.resolved_questions)
        self.assertEqual(out.screening_status, "journal-article-metadata")

    def test_post_publication_update_is_flagged(self):
        item = {
            "DOI": "10.1234/corrected",
            "title": ["Corrected result"],
            "container-title": ["Example Journal"],
            "type": "journal-article",
            "published": {"date-parts": [[2026, 9, 20]]},
            "update-to": [{"DOI": "10.1234/original", "type": "correction"}],
            "abstract": "<jats:p>This updated analysis reports a correction and limitations.</jats:p>",
        }
        out = CriticalAppraiser().review(item)
        self.assertIn("update-to", out.update_flags)
        self.assertIn("post-publication-update-flag", out.screening_status)


if __name__ == "__main__":
    unittest.main()
