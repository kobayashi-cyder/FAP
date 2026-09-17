from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, List

from .models import BenchmarkCase, BenchmarkResult


class JsonlBenchmark:
    """Runs local task JSONL with a supplied solver callback. No dataset-specific answer hardcoding."""

    def __init__(self, paths: dict, solver: Callable[[BenchmarkCase], dict]):
        self.paths = {k: Path(v) for k, v in paths.items()}
        self.solver = solver

    def run(self, split: str) -> Iterable[BenchmarkResult]:
        out: List[BenchmarkResult] = []
        with self.paths[split].open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                case = BenchmarkCase(
                    case_id=row["id"], domain=row.get("domain", "unknown"),
                    task=row["task"], expected=row.get("expected"), metadata=row.get("metadata", {}),
                )
                result = self.solver(case)
                actual = result.get("actual")
                success = bool(result.get("success", actual == case.expected))
                out.append(BenchmarkResult(
                    case=case, success=success, actual=actual, error=result.get("error", ""),
                    latency_ms=float(result.get("latency_ms", 0.0)),
                    teacher_used=bool(result.get("teacher_used", False)),
                    verified=bool(result.get("verified", False)),
                    verifier_confidence=float(result.get("verifier_confidence", 0.0)),
                    metadata=result.get("metadata", {}),
                ))
        return out
