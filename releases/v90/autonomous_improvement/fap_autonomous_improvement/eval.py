from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    ability: str
    payload: Any
    expected: Any
    difficulty: float = 0.5
    evaluator: Callable[[Any, Any], bool] = field(
        default=lambda actual, expected: actual == expected,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True)
class EvalObservation:
    case_id: str
    ability: str
    difficulty: float
    passed: bool
    actual: Any
    expected: Any
    error: str = ""


@dataclass(frozen=True)
class EvalResult:
    total: int
    passed: int
    failed: int
    accuracy: float
    by_ability: dict[str, dict[str, Any]]
    observations: tuple[EvalObservation, ...]

    @property
    def failures(self) -> tuple[EvalObservation, ...]:
        return tuple(row for row in self.observations if not row.passed)


class FAPEval:
    """Independent benchmark harness used before and after autonomous changes."""

    def __init__(self, cases: Sequence[EvalCase]):
        rows = tuple(cases)
        if not rows:
            raise ValueError("FAP-Eval requires at least one case")
        ids = [str(case.case_id).strip() for case in rows]
        if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
            raise ValueError("FAP-Eval case_id values must be unique and non-empty")
        for case in rows:
            if not str(case.ability).strip():
                raise ValueError("FAP-Eval ability is required")
            if not 0.0 <= float(case.difficulty) <= 1.0:
                raise ValueError("FAP-Eval difficulty must be in [0,1]")
            if not callable(case.evaluator):
                raise TypeError("FAP-Eval evaluator must be callable")
        self.cases = rows

    def run(self, solver: Callable[[EvalCase], Any]) -> EvalResult:
        if not callable(solver):
            raise TypeError("FAP-Eval solver must be callable")
        observations: list[EvalObservation] = []
        for case in self.cases:
            try:
                actual = solver(case)
                passed = bool(case.evaluator(actual, case.expected))
                error = ""
            except Exception as exc:
                actual = None
                passed = False
                error = f"{type(exc).__name__}:{exc}"
            observations.append(
                EvalObservation(
                    case.case_id,
                    case.ability,
                    float(case.difficulty),
                    passed,
                    actual,
                    case.expected,
                    error,
                )
            )

        by_ability: dict[str, dict[str, Any]] = {}
        for row in observations:
            bucket = by_ability.setdefault(
                row.ability,
                {"total": 0, "passed": 0, "failed": 0, "accuracy": 0.0},
            )
            bucket["total"] += 1
            if row.passed:
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
        for bucket in by_ability.values():
            bucket["accuracy"] = (
                bucket["passed"] / bucket["total"]
                if bucket["total"]
                else 0.0
            )

        passed = sum(1 for row in observations if row.passed)
        total = len(observations)
        return EvalResult(
            total,
            passed,
            total - passed,
            passed / total if total else 0.0,
            by_ability,
            tuple(observations),
        )

    @staticmethod
    def failure_clusters(result: EvalResult) -> dict[str, list[EvalObservation]]:
        clusters: dict[str, list[EvalObservation]] = {}
        for row in result.failures:
            clusters.setdefault(row.ability, []).append(row)
        return clusters
