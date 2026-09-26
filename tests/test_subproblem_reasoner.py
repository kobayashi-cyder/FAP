from __future__ import annotations

from pathlib import Path
import unittest

from fap_subproblem_reasoner import SubproblemReasoner


ROOT = Path(__file__).resolve().parents[1]


class SubproblemReasonerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reasoner = SubproblemReasoner(ROOT)

    def test_splits_two_explicit_intents(self):
        parts = self.reasoner.split(
            "2+3を計算して。エントロピーについて説明して。"
        )
        self.assertEqual(len(parts), 2)
        self.assertIn("2+3", parts[0].text)
        self.assertIn("エントロピー", parts[1].text)

    def test_combines_verified_math_and_grounded_knowledge(self):
        out = self.reasoner.run(
            "2+3を計算して。エントロピーについて説明して。"
        )
        self.assertIsNotNone(out)
        self.assertTrue(out["subproblem_reasoning"])
        self.assertEqual(out["subproblem_count"], 2)
        self.assertEqual(out["subproblem_solved"], 2)
        self.assertEqual(out["subproblem_coverage"], 1.0)
        self.assertIn("5", out["reply"])
        self.assertIn("エントロピー", out["reply"])
        self.assertFalse(out["needs_teacher"])

    def test_unknown_segment_is_not_fabricated(self):
        out = self.reasoner.run(
            "2+3を計算して。ZXQV-UNKNOWN-93について説明して。"
        )
        self.assertIsNone(out)

    def test_fenced_code_is_not_naively_split(self):
        text = """Pythonを確認して。
```python
x = 1
print(x)
```
さらに2+2を計算して。
"""
        self.assertEqual(self.reasoner.split(text), [])


if __name__ == "__main__":
    unittest.main()
