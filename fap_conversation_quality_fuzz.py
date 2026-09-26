from __future__ import annotations

from dataclasses import dataclass
import random
import re
import string
from typing import Iterable

from fap_reflective_conversation import CONCEPTS, Concept


_GENERIC_WRAPPERS = (
    "{subject}について説明して",
    "{subject}とは？",
    "{subject}を簡単に説明して",
    "{subject}の仕組みは？",
    "{subject}をもう少し詳しく",
)

_CONTEXT_ONLY_FOLLOWUPS = (
    "どういうこと？",
    "つまり？",
    "もう少し簡単に",
    "それってどういう意味？",
    "その点をもう一度説明して",
)

_EXPLICIT_CLARIFIERS = (
    "{subject}ってどういうこと？",
    "{subject}とはどういう意味？",
    "{subject}について簡単に説明して",
)


@dataclass(frozen=True)
class QualityCase:
    kind: str
    concept_id: str
    prompt: str
    history_concept_id: str = ""
    expected_topic_id: str = ""


def _fullwidth_ascii(text: str) -> str:
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch == " ":
            out.append("\u3000")
        elif 0x21 <= code <= 0x7E:
            out.append(chr(code + 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def _punctuate(text: str, rng: random.Random) -> str:
    value = str(text)
    if len(value) < 4:
        return value
    positions = [i for i in range(1, len(value)) if value[i - 1].isalnum() and value[i].isalnum()]
    if not positions:
        return value
    pos = rng.choice(positions)
    return value[:pos] + rng.choice(("・", "／", "－", "　")) + value[pos:]


def _variant(alias: str, rng: random.Random, mode: int) -> str:
    if mode == 0:
        return alias
    if mode == 1:
        return _fullwidth_ascii(alias)
    if mode == 2:
        return _punctuate(alias, rng)
    if mode == 3:
        return " ".join(alias)
    if mode == 4:
        return alias.swapcase()
    return f"「{alias}」"


def _unknown_token(rng: random.Random) -> str:
    # Latin-only synthetic labels avoid accidental matches with local Japanese
    # concepts while still behaving like an explicit user-supplied subject.
    body = "".join(rng.choice(string.ascii_lowercase) for _ in range(14))
    return "qx" + body + "zv"


def _concept_by_id(concept_id: str) -> Concept:
    for concept in CONCEPTS:
        if concept.concept_id == concept_id:
            return concept
    raise KeyError(concept_id)


def history_for(concept_id: str) -> list[dict]:
    concept = _concept_by_id(concept_id)
    subject = concept.aliases[0]
    return [
        {"role": "user", "text": f"{subject}について説明して"},
        {"role": "assistant", "text": concept.summary},
    ]


def generate_quality_cases(*, seed: int, rounds: int = 8) -> Iterable[QualityCase]:
    rng = random.Random(int(seed))
    concepts = tuple(CONCEPTS)
    if not concepts or rounds <= 0:
        return ()

    rows: list[QualityCase] = []
    for index in range(int(rounds)):
        concept = concepts[index % len(concepts)]
        alias = rng.choice(concept.aliases)
        variant = _variant(alias, rng, index % 6)
        rows.append(
            QualityCase(
                kind="semantic_stability",
                concept_id=concept.concept_id,
                prompt=rng.choice(_GENERIC_WRAPPERS).format(subject=variant),
                expected_topic_id=concept.concept_id,
            )
        )

        history_concept = concepts[(index + 1) % len(concepts)]
        rows.append(
            QualityCase(
                kind="subjectless_followup",
                concept_id=history_concept.concept_id,
                prompt=rng.choice(_CONTEXT_ONLY_FOLLOWUPS),
                history_concept_id=history_concept.concept_id,
                expected_topic_id=history_concept.concept_id,
            )
        )

        unknown = _unknown_token(rng)
        rows.append(
            QualityCase(
                kind="explicit_unknown_isolation",
                concept_id="",
                prompt=rng.choice(_EXPLICIT_CLARIFIERS).format(subject=unknown),
                history_concept_id=history_concept.concept_id,
                expected_topic_id="",
            )
        )

        current = concepts[(index + 2) % len(concepts)]
        current_alias = rng.choice(current.aliases)
        rows.append(
            QualityCase(
                kind="current_turn_override",
                concept_id=current.concept_id,
                prompt=rng.choice(_GENERIC_WRAPPERS).format(subject=current_alias),
                history_concept_id=history_concept.concept_id,
                expected_topic_id=current.concept_id,
            )
        )

    rng.shuffle(rows)
    return tuple(rows)


def repeated_sentence_ratio(text: str) -> float:
    pieces = [
        x.strip()
        for x in re.split(r"[。！？!?\n]+", str(text or ""))
        if x.strip()
    ]
    if not pieces:
        return 0.0
    repeated = len(pieces) - len(set(pieces))
    return repeated / len(pieces)


def has_internal_error_marker(text: str) -> bool:
    value = str(text or "").casefold()
    markers = (
        "traceback (most recent call last)",
        "internal server error",
        "assertionerror",
        "typeerror:",
        "valueerror:",
    )
    return any(marker in value for marker in markers)
