from __future__ import annotations

import unittest

from fap_response_explorers import (
    CausalGraphExplorer,
    CounterexampleConditionExplorer,
    LongFormContradictionExplorer,
    MultiStepMathExplorer,
    PythonRepairExplorer,
)


class ResponseExplorerTests(unittest.TestCase):
    def test_multi_step_math_keeps_independent_branches(self) -> None:
        out = MultiStepMathExplorer().run("計算: 2+3 と 4*5 をそれぞれ求めて")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertEqual(len(out.get("branches", [])), 2)
        values = [row.get("value") for row in out.get("branches", [])]
        self.assertIn(5, values)
        self.assertIn(20, values)

    def test_python_repair_reparses_candidate_without_execution(self) -> None:
        text = """Pythonコードを修復して
```python
def broken(:
    return 1
```
"""
        out = PythonRepairExplorer().run(text)
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertTrue(out.get("python_repair_verified_syntax"))
        self.assertIn("def broken():", out.get("repaired_source", ""))

    def test_causal_graph_uses_only_explicit_edges(self) -> None:
        out = CausalGraphExplorer().run("A -> B。B -> C")
        self.assertIsNotNone(out)
        self.assertEqual(len(out.get("edges", [])), 2)
        self.assertEqual(out.get("paths", [])[0].get("source"), "A")
        self.assertEqual(out.get("paths", [])[0].get("target"), "C")
        self.assertFalse(out.get("verified"))

    def test_counterexample_explorer_states_falsification_condition(self) -> None:
        out = CounterexampleConditionExplorer().run("すべての白鳥は白い。反例を探して")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("counterexample_exploration"))
        self.assertIn("反証", out.get("reply", ""))

    def test_longform_contradiction_crosses_history(self) -> None:
        history = [{"role": "user", "text": "mode=enabled"}]
        out = LongFormContradictionExplorer().run("mode=disabled", history)
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertTrue(out.get("longform_contradiction_verified"))
        self.assertIn("mode", out.get("reply", ""))


if __name__ == "__main__":
    unittest.main()
