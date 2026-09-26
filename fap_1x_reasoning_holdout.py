from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import random
from pathlib import Path

from fap_1x_reasoning_core import FAP1xGeneralReasoningCore


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class HoldoutReport:
    version: str
    seed: int
    passed: int
    total: int
    score: float
    categories: dict[str, dict[str, int]]

    def to_dict(self) -> dict:
        return asdict(self)


def _seed() -> int:
    raw = os.environ.get("FAP_REASONING_HOLDOUT_SEED", "").strip()
    if raw:
        return int(raw, 0)
    return random.SystemRandom().randrange(1, 2**63)


def _mcq(question: str, choices: list[str]) -> str:
    return (
        "Answer the following multiple choice question.\n"
        "The last line of your response should be: Answer: $LETTER\n\n"
        + question
        + "\n\n"
        + "\n".join(
            f"{letter}) {value}"
            for letter, value in zip("ABCD", choices)
        )
    )


def _place_answer(
    rng: random.Random,
    correct: str,
    distractors: list[str],
) -> tuple[list[str], str]:
    values = [correct, *distractors[:3]]
    rng.shuffle(values)
    return values, "ABCD"[values.index(correct)]


def _record(stats: dict[str, dict[str, int]], category: str, ok: bool) -> None:
    row = stats.setdefault(category, {"passed": 0, "total": 0})
    row["total"] += 1
    row["passed"] += int(bool(ok))


def run_holdout(seed: int | None = None) -> HoldoutReport:
    seed = int(_seed() if seed is None else seed)
    rng = random.Random(seed)
    core = FAP1xGeneralReasoningCore(ROOT)
    stats: dict[str, dict[str, int]] = {}

    # Fresh arithmetic values and shuffled answers.
    for _ in range(12):
        a = rng.randrange(3, 500)
        b = rng.randrange(2, 200)
        op = rng.choice(["+", "-", "*"])
        value = {"+": a + b, "-": a - b, "*": a * b}[op]
        distractors = [
            str(value + rng.choice([1, 2, 3, 5])),
            str(value - rng.choice([1, 2, 4, 7])),
            str(value + rng.choice([9, 11, 13])),
        ]
        choices, answer = _place_answer(rng, str(value), distractors)
        result = core.solve(_mcq(f"What is {a} {op} {b}?", choices))
        ok = bool(
            result
            and result.get("verification_state") == "verified"
            and result.get("reasoning_source") == "verified_arithmetic"
            and f"Answer: ${answer}" in str(result.get("reply"))
        )
        _record(stats, "generated_arithmetic", ok)

    # Fresh Ohm-law cases; numerical values and option positions are unseen.
    for _ in range(10):
        current = rng.randrange(1, 15)
        resistance = rng.randrange(1, 40)
        voltage = current * resistance
        choices, answer = _place_answer(
            rng,
            f"{voltage} V",
            [
                f"{voltage + current} V",
                f"{max(0, voltage - resistance)} V",
                f"{voltage + resistance} V",
            ],
        )
        wording = rng.choice([
            f"In an Ohm's law circuit, current is {current} A and resistance is {resistance} ohms. What is the voltage?",
            f"For Ohm's law, current = {current} A and resistance = {resistance} ohms. Find the voltage.",
        ])
        result = core.solve(_mcq(wording, choices))
        ok = bool(
            result
            and result.get("verification_state") == "verified"
            and result.get("reasoning_source") == "deterministic_physics"
            and f"Answer: ${answer}" in str(result.get("reply"))
        )
        _record(stats, "generated_ohms_law", ok)

    # Unknown tasks must never be converted into a forced A-D guess.
    for _ in range(8):
        nonce = f"ZXQV-{rng.randrange(10**8, 10**9)}"
        choices = [f"claim-{rng.randrange(10**5, 10**6)}" for _ in range(4)]
        result = core.solve(_mcq(f"Which option is correct about {nonce}?", choices))
        reply = str((result or {}).get("reply", ""))
        ok = bool(
            result
            and result.get("verification_state") == "unresolved"
            and result.get("reasoning_source") == "fail_closed"
            and "Answer:" not in reply
        )
        _record(stats, "unknown_abstention", ok)

    # Context-dependent rule reasoning must resolve the subject from history.
    aliases = ["四角形", "長方形", "正方形", "平行四辺形"]
    for _ in range(6):
        alias = rng.choice(aliases)
        history = (
            {"role": "user", "text": f"{alias}について考える"},
            {"role": "assistant", "text": "続けてください"},
        )
        result = core.solve("内角の和は？", history)
        ok = bool(
            result
            and result.get("verification_state") == "verified"
            and result.get("reasoning_source") == "rule_verified"
            and "360" in str(result.get("reply"))
        )
        _record(stats, "contextual_rule_reasoning", ok)

    # Symbolic derivation uses an algebraic entailment plus countercheck.
    for prompt in (
        "三平方の定理を導出して",
        "中点公式を証明して",
        "対称な差の関係を導いて",
    ):
        result = core.solve(prompt)
        ok = bool(
            result
            and result.get("verification_state") == "verified"
            and result.get("reasoning_source") == "derivation_verified"
        )
        _record(stats, "symbolic_derivation", ok)

    total = sum(row["total"] for row in stats.values())
    passed = sum(row["passed"] for row in stats.values())
    return HoldoutReport(
        version="fap.1.0.01.reasoning_holdout.v1",
        seed=seed,
        passed=passed,
        total=total,
        score=passed / max(1, total),
        categories=stats,
    )


def main() -> int:
    report = run_holdout()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
