from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import random

from fap_1x_reasoning_holdout import run_holdout


@dataclass(frozen=True)
class StressReport:
    version: str
    base_seed: int
    rounds: int
    passed: int
    total: int
    score: float
    worst_round_score: float
    seeds: tuple[int, ...]
    round_scores: tuple[float, ...]

    def to_dict(self):
        return asdict(self)


def _base_seed() -> int:
    raw = os.environ.get("FAP_REASONING_STRESS_SEED", "").strip()
    if raw:
        return int(raw, 0)
    return random.SystemRandom().randrange(1, 2**63)


def run_stress(base_seed: int | None = None, rounds: int = 8) -> StressReport:
    base_seed = int(_base_seed() if base_seed is None else base_seed)
    rounds = max(1, min(32, int(rounds)))
    rng = random.Random(base_seed)
    seeds = tuple(rng.randrange(1, 2**63) for _ in range(rounds))
    reports = tuple(run_holdout(seed) for seed in seeds)
    passed = sum(report.passed for report in reports)
    total = sum(report.total for report in reports)
    scores = tuple(report.score for report in reports)
    return StressReport(
        version="fap.1.0.01.reasoning_stress.v1",
        base_seed=base_seed,
        rounds=rounds,
        passed=passed,
        total=total,
        score=passed / max(1, total),
        worst_round_score=min(scores) if scores else 0.0,
        seeds=seeds,
        round_scores=scores,
    )


def main() -> int:
    report = run_stress()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
