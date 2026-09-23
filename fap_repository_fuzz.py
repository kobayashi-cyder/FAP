from __future__ import annotations

from dataclasses import asdict, dataclass
import random
from typing import Iterable


@dataclass(frozen=True)
class FuzzLexicon:
    verbs: tuple[str, ...]
    targets: tuple[str, ...]
    qualifiers: tuple[str, ...] = ()
    conjunctions: tuple[str, ...] = (" and ", " then ")


@dataclass(frozen=True)
class CodingFuzzCase:
    case_id: str
    seed: int
    goal: str
    components: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryCodingFuzzer:
    """Deterministic corpus generator for repository-coding robustness tests.

    The generator is data-driven: callers provide the lexicon. It does not
    contain task-specific expected answers and produces reproducible cases from
    a seed for regression triage.
    """

    VERSION = "fap.repository.coding_fuzz.v1"

    def __init__(self, lexicon: FuzzLexicon) -> None:
        if not lexicon.verbs or not lexicon.targets:
            raise ValueError("verbs and targets must be non-empty")
        self.lexicon = lexicon

    def generate(
        self,
        *,
        seed: int,
        count: int,
        max_clauses: int = 3,
    ) -> tuple[CodingFuzzCase, ...]:
        if not 1 <= int(count) <= 100_000:
            raise ValueError("count must be in [1, 100000]")
        if not 1 <= int(max_clauses) <= 8:
            raise ValueError("max_clauses must be in [1, 8]")

        rng = random.Random(int(seed))
        out: list[CodingFuzzCase] = []
        seen: set[str] = set()
        attempts = 0
        attempt_limit = max(100, int(count) * 20)

        while len(out) < int(count) and attempts < attempt_limit:
            attempts += 1
            clause_count = rng.randint(1, int(max_clauses))
            components: list[str] = []
            clauses: list[str] = []
            for _ in range(clause_count):
                verb = rng.choice(self.lexicon.verbs)
                target = rng.choice(self.lexicon.targets)
                qualifier = (
                    rng.choice(self.lexicon.qualifiers)
                    if self.lexicon.qualifiers and rng.random() < 0.7
                    else ""
                )
                clause = " ".join(x for x in (verb, target, qualifier) if x).strip()
                clauses.append(clause)
                components.extend(x for x in (verb, target, qualifier) if x)

            goal = clauses[0]
            for clause in clauses[1:]:
                joiner = rng.choice(self.lexicon.conjunctions)
                goal += joiner + clause

            if goal in seen:
                continue
            seen.add(goal)
            index = len(out)
            out.append(
                CodingFuzzCase(
                    case_id=f"fuzz-{seed}-{index:06d}",
                    seed=int(seed),
                    goal=goal,
                    components=tuple(components),
                )
            )

        if len(out) != int(count):
            raise ValueError(
                f"lexicon could only generate {len(out)} unique cases for requested {count}"
            )
        return tuple(out)


def classify_failure(errors: Iterable[str]) -> tuple[str, ...]:
    """Collapse arbitrary error text into bounded stable categories."""
    out: list[str] = []
    for raw in errors:
        text = str(raw or "").strip()
        if not text:
            continue
        pieces = text.split(":")
        category = ":".join(pieces[:2]) if len(pieces) >= 2 else pieces[0]
        category = category[:160]
        if category not in out:
            out.append(category)
    return tuple(out)
