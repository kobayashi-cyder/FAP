from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class CodingBenchmarkCase:
    case_id: str
    goal: str
    expected_state: str = "verified_candidate"


@dataclass(frozen=True)
class CodingBenchmarkCaseResult:
    case_id: str
    expected_state: str
    observed_state: str
    passed: bool
    duration_ms: int
    repairs_used: int
    edited_files: int
    error_categories: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CodingBenchmarkReport:
    version: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    total_duration_ms: int
    total_repairs: int
    total_edited_files: int
    results: tuple[CodingBenchmarkCaseResult, ...]

    def to_dict(self) -> dict:
        return asdict(self)


BenchmarkExecutor = Callable[[str], Any]


class RepositoryCodingBenchmark:
    """Small deterministic harness for comparing repository-coding changes.

    The benchmark never mutates a repository itself. It invokes a supplied
    coding executor and records stable outcome metrics so horizontal branches
    can compare behavior without inventing version numbers or ad-hoc scores.
    """

    VERSION = "fap.repository.benchmark.v1"

    def run(
        self,
        cases: Iterable[CodingBenchmarkCase],
        executor: BenchmarkExecutor,
    ) -> CodingBenchmarkReport:
        rows = tuple(cases)
        if not rows:
            raise ValueError("at least one benchmark case is required")
        if not callable(executor):
            raise TypeError("executor must be callable")

        seen: set[str] = set()
        results: list[CodingBenchmarkCaseResult] = []
        for case in rows:
            case_id = str(case.case_id or "").strip()
            goal = str(case.goal or "").strip()
            expected = str(case.expected_state or "").strip()
            if not case_id or not goal or not expected:
                raise ValueError("benchmark case fields must be non-empty")
            if case_id in seen:
                raise ValueError(f"duplicate benchmark case_id: {case_id}")
            seen.add(case_id)

            started = perf_counter()
            try:
                output = executor(goal)
                observed = str(getattr(output, "state", "unknown") or "unknown")
                repairs = _repairs_used(output)
                edited = _edited_files(output)
                errors = _error_categories(getattr(output, "errors", ()))
            except Exception as exc:
                observed = "executor_error"
                repairs = 0
                edited = 0
                errors = (f"executor_error:{type(exc).__name__}",)
            elapsed = max(0, int((perf_counter() - started) * 1000))
            results.append(
                CodingBenchmarkCaseResult(
                    case_id=case_id,
                    expected_state=expected,
                    observed_state=observed,
                    passed=observed == expected,
                    duration_ms=elapsed,
                    repairs_used=repairs,
                    edited_files=edited,
                    error_categories=errors,
                )
            )

        passed = sum(1 for row in results if row.passed)
        return CodingBenchmarkReport(
            version=self.VERSION,
            total_cases=len(results),
            passed_cases=passed,
            pass_rate=round(passed / len(results), 6),
            total_duration_ms=sum(row.duration_ms for row in results),
            total_repairs=sum(row.repairs_used for row in results),
            total_edited_files=sum(row.edited_files for row in results),
            results=tuple(results),
        )


def _repairs_used(output: Any) -> int:
    repair = getattr(output, "repair", None)
    value = getattr(repair, "repairs_used", 0) if repair is not None else 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _edited_files(output: Any) -> int:
    rows = getattr(output, "final_edits", ())
    try:
        return len(tuple(rows))
    except TypeError:
        return 0


def _error_categories(errors: Any) -> tuple[str, ...]:
    out: list[str] = []
    try:
        rows = tuple(errors or ())
    except TypeError:
        rows = (errors,)
    for raw in rows:
        text = str(raw or "").strip()
        if not text:
            continue
        pieces = text.split(":")
        category = ":".join(pieces[:2]) if len(pieces) >= 2 else pieces[0]
        if category not in out:
            out.append(category[:160])
    return tuple(out)
