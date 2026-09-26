from __future__ import annotations

import unittest

from fap_response_specialists_extra import (
    LinearEquationSpecialist,
    NumericContradictionSpecialist,
    PhysicsNumericSpecialist,
    PythonStaticAnalysisSpecialist,
)


class ResponseExtraSpecialistTests(unittest.TestCase):
    def test_linear_equation_solver(self) -> None:
        out = LinearEquationSpecialist().run("方程式 2x + 3 = 11 を解いて")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertIn("x = 4", out.get("reply", ""))

    def test_zero_solution_linear_equation(self) -> None:
        out = LinearEquationSpecialist().run("方程式 6x - 1 = -1 を解いて")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertIn("x = 0", out.get("reply", ""))

    def test_physics_force_solver(self) -> None:
        out = PhysicsNumericSpecialist().run(
            "質量=2 kg、加速度=3 m/s^2 のとき力を求めて"
        )
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertEqual(out.get("formula"), "F=ma")
        self.assertAlmostEqual(float(out.get("value")), 6.0)

    def test_python_static_analysis_never_executes(self) -> None:
        text = """Pythonコードを確認して
```python
import subprocess
def f(x):
    return eval(x)
```
"""
        out = PythonStaticAnalysisSpecialist().run(text)
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertTrue(out.get("syntax_ok"))
        self.assertIn("forbidden_import:subprocess", out.get("issues", []))
        self.assertIn("forbidden_call:eval", out.get("issues", []))

    def test_python_syntax_error_is_reported_as_static_fact(self) -> None:
        text = """Pythonコードを確認して
```python
def broken(:
    pass
```
"""
        out = PythonStaticAnalysisSpecialist().run(text)
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertFalse(out.get("syntax_ok"))

    def test_numeric_contradiction_across_history(self) -> None:
        history = [
            {"role": "user", "text": "temperature=20 C"},
            {"role": "assistant", "text": "temperature=20 C として扱います"},
        ]
        out = NumericContradictionSpecialist().run("temperature=25 C", history)
        self.assertIsNotNone(out)
        self.assertTrue(out.get("verified"))
        self.assertIn("20", out.get("reply", ""))
        self.assertIn("25", out.get("reply", ""))


if __name__ == "__main__":
    unittest.main()
