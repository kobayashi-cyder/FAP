from __future__ import annotations

from dataclasses import asdict, dataclass
import random
import re
from typing import Iterable


_SAFE_CATEGORY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_STRUCTURAL_TOKEN = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_SAFE_EXCEPTION = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,79}(?:Error|Exception)$")
_STRUCTURED_SECOND_FIELD = frozenset(
    {
        "proposal_provider_failed",
        "execution_pipeline_failed",
        "command_policy",
        "focused_command_failed",
        "regression_command_failed",
        "plan_not_ready",
    }
)
_FALLBACK_FAILURE = "unclassified_failure"


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
        if int(max_clauses) > 1 and not self.lexicon.conjunctions:
            raise ValueError(
                "conjunctions must be non-empty when max_clauses > 1"
            )

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
    """Collapse arbitrary error text into bounded, non-sensitive categories."""

    out: list[str] = []
    for raw in errors:
        text = str(raw or "").strip()
        if not text:
            continue

        pieces = [piece.strip() for piece in text.split(":")]
        first = pieces[0] if pieces else ""

        if _SAFE_EXCEPTION.fullmatch(first):
            category = f"exception:{first}"
        elif not _SAFE_CATEGORY.fullmatch(first):
            category = _FALLBACK_FAILURE
        elif (
            first in _STRUCTURED_SECOND_FIELD
            and len(pieces) >= 2
            and _SAFE_STRUCTURAL_TOKEN.fullmatch(pieces[1])
        ):
            category = f"{first}:{pieces[1]}"
        else:
            category = first

        if category not in out:
            out.append(category)

    return tuple(out)
