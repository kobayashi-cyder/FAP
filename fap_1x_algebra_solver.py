from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any, Mapping

from fap_benchmark_reasoning import MCQTask, StructuredMCQParser
from fap_generic_derivation import parse_equation


@dataclass(frozen=True)
class AlgebraResult:
    variable: str
    value: Fraction
    equation: str
    verified: bool
    answer_letter: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "value": (
                str(self.value.numerator)
                if self.value.denominator == 1
                else "{}/{}".format(self.value.numerator, self.value.denominator)
            ),
            "equation": self.equation,
            "verified": self.verified,
            "answer_letter": self.answer_letter,
        }


class GenericLinearEquationSolver:
    """Safe one-variable linear equation solver with substitution check."""

    _EQ = re.compile(
        r"([0-9A-Za-z_+\-*/^().\s]+=[0-9A-Za-z_+\-*/^().\s]+)"
    )

    @staticmethod
    def _normalize_implicit_multiplication(expr: str) -> str:
        value = re.sub(r"(?<=\d)(?=[A-Za-z])", "*", expr)
        value = re.sub(r"(?<=[A-Za-z])(?=\d)", "*", value)
        return value

    @staticmethod
    def _fraction_text(value: Fraction) -> str:
        return (
            str(value.numerator)
            if value.denominator == 1
            else "{}/{}".format(value.numerator, value.denominator)
        )

    @staticmethod
    def _extract_linear_coefficients(poly, variable: str) -> tuple[Fraction, Fraction] | None:
        a = Fraction(0)
        b = Fraction(0)
        for mono, coeff in poly.items():
            if not mono:
                b += coeff
                continue
            if mono == ((variable, 1),):
                a += coeff
                continue
            return None
        return a, b

    def solve_equation(self, equation: str, variable: str) -> AlgebraResult | None:
        eq = self._normalize_implicit_multiplication(equation)
        try:
            _lhs, _rhs, diff = parse_equation(eq)
        except (SyntaxError, ValueError, ZeroDivisionError):
            return None
        coefficients = self._extract_linear_coefficients(diff, variable)
        if coefficients is None:
            return None
        a, b = coefficients
        if a == 0:
            return None
        value = -b / a
        verified = (a * value + b) == 0
        if not verified:
            return None
        return AlgebraResult(
            variable=variable,
            value=value,
            equation=eq,
            verified=True,
        )

    @staticmethod
    def _equation_candidates(text: str) -> list[str]:
        query = str(text or "").replace("：", ":")
        out: list[str] = []
        for segment in re.split(r"[?？。!！;；\n]", query):
            if "=" not in segment:
                continue
            left_raw, right_raw = segment.split("=", 1)
            left_tokens = re.findall(r"[^\s,:]+", left_raw)
            right_tokens = re.findall(r"[^\s,:]+", right_raw)
            valid = re.compile(r"^[0-9A-Za-z_+\-*/^().]+$")
            left_tail: list[str] = []
            for token in reversed(left_tokens):
                if not valid.fullmatch(token):
                    break
                if re.search(r"[A-Za-z]{2,}", token):
                    break
                left_tail.append(token)
            left_tail.reverse()
            right_head: list[str] = []
            for token in right_tokens:
                if not valid.fullmatch(token):
                    break
                if re.search(r"[A-Za-z]{2,}", token):
                    break
                right_head.append(token)
            if not left_tail or not right_head:
                continue
            # Short suffix/prefix pairs are attempted first so instruction
            # fragments such as "for x" are not absorbed into the equation.
            for li in range(len(left_tail) - 1, -1, -1):
                lhs = "".join(left_tail[li:])
                for rj in range(1, len(right_head) + 1):
                    rhs = "".join(right_head[:rj])
                    candidate = lhs + "=" + rhs
                    if candidate not in out:
                        out.append(candidate)
        return out

    def _from_text(self, text: str) -> AlgebraResult | None:
        for equation in self._equation_candidates(text):
            variables = sorted(set(re.findall(r"[A-Za-z]", equation)))
            variables = [v for v in variables if v.lower() not in {"e"}]
            if len(variables) != 1:
                continue
            result = self.solve_equation(equation, variables[0])
            if result is not None:
                return result
        return None

    @staticmethod
    def _choice_fraction(text: str) -> Fraction | None:
        value = str(text or "").strip().replace(",", "")
        value = re.sub(r"^[A-Za-z]\s*=\s*", "", value)
        value = value.strip("$ ")
        if re.fullmatch(r"[-+]?\d+", value):
            return Fraction(int(value), 1)
        if re.fullmatch(r"[-+]?\d+\s*/\s*[-+]?\d+", value):
            left, right = value.split("/", 1)
            if int(right) == 0:
                return None
            return Fraction(int(left), int(right))
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
            return Fraction(value)
        return None

    def solve_mcq(self, task: MCQTask) -> AlgebraResult | None:
        result = self._from_text(task.question)
        if result is None:
            return None
        matches = [
            letter
            for letter, choice in task.choices.items()
            if self._choice_fraction(choice) == result.value
        ]
        if len(matches) != 1:
            return None
        return AlgebraResult(
            variable=result.variable,
            value=result.value,
            equation=result.equation,
            verified=True,
            answer_letter=matches[0],
        )

    def run(
        self,
        text: str,
        history: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        parser = StructuredMCQParser()
        task = parser.parse(text)
        if task is not None:
            result = self.solve_mcq(task)
            if result is None:
                return None
            value_text = self._fraction_text(result.value)
            reply = "{} を整理すると {}={}。".format(
                result.equation,
                result.variable,
                value_text,
            ) + "\nAnswer: $" + result.answer_letter
            return {
                "ok": True,
                "reply": reply,
                "confidence": 0.98,
                "needs_teacher": False,
                "linear_algebra_solver": True,
                "algebra_verified": True,
                "algebra_result": result.to_dict(),
                "decision_source": "generic_linear_equation",
            }

        result = self._from_text(text)
        if result is None:
            return None
        value_text = self._fraction_text(result.value)
        return {
            "ok": True,
            "reply": "{} を整理すると {}={} です。".format(
                result.equation,
                result.variable,
                value_text,
            ),
            "confidence": 0.98,
            "needs_teacher": False,
            "linear_algebra_solver": True,
            "algebra_verified": True,
            "algebra_result": result.to_dict(),
            "decision_source": "generic_linear_equation",
        }
