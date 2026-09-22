from __future__ import annotations

from dataclasses import dataclass
import random
import string
from typing import Iterable

from fap_reflective_conversation import CONCEPTS, Concept


_FOLLOWUPS = (
    "それってどういう意味？",
    "つまり？",
    "その点をもう少し",
    "どういうこと？",
)

_ACKS = (
    "ありがとう",
    "なるほど",
    "了解",
    "わかりました",
)

_CORRECTION_FRAMES = (
    "{old}ではなく{new}について説明して",
    "{old}じゃなくて{new}について教えて",
    "{old}ではなく、{new}のほう",
)


@dataclass(frozen=True)
class MultiTurnCase:
    kind: str
    prompt: str
    history: tuple[dict, ...]
    expected_topic_id: str = ""
    expect_resolved: bool = False


def _unknown_token(rng: random.Random) -> str:
    body = "".join(rng.choice(string.ascii_lowercase) for _ in range(16))
    return "qz" + body + "vx"


def _history_exchange(concept: Concept) -> list[dict]:
    subject = concept.aliases[0]
    return [
        {"role": "user", "text": f"{subject}について説明して"},
        {"role": "assistant", "text": concept.summary},
    ]


def generate_multiturn_cases(*, seed: int, rounds: int = 32) -> Iterable[MultiTurnCase]:
    rng = random.Random(int(seed))
    concepts = tuple(CONCEPTS)
    if len(concepts) < 2 or rounds <= 0:
        return ()

    rows: list[MultiTurnCase] = []
    for i in range(int(rounds)):
        old = concepts[i % len(concepts)]
        latest = concepts[(i + 1) % len(concepts)]

        history = _history_exchange(old) + _history_exchange(latest)
        rows.append(
            MultiTurnCase(
                kind="latest_known_wins",
                prompt=rng.choice(_FOLLOWUPS),
                history=tuple(history),
                expected_topic_id=latest.concept_id,
                expect_resolved=True,
            )
        )

        unknown = _unknown_token(rng)
        stale_history = _history_exchange(old) + [
            {"role": "user", "text": f"{unknown}とはどういう意味？"},
            {"role": "assistant", "text": "その語についてローカル根拠がありません。"},
        ]
        rows.append(
            MultiTurnCase(
                kind="unknown_subject_blocks_stale_resurrection",
                prompt=rng.choice(_FOLLOWUPS),
                history=tuple(stale_history),
                expected_topic_id="",
                expect_resolved=False,
            )
        )

        correction_old = concepts[(i + 2) % len(concepts)]
        correction_new = concepts[(i + 3) % len(concepts)]
        old_alias = rng.choice(correction_old.aliases)
        new_alias = rng.choice(correction_new.aliases)
        correction = rng.choice(_CORRECTION_FRAMES).format(
            old=old_alias,
            new=new_alias,
        )
        rows.append(
            MultiTurnCase(
                kind="explicit_correction_switch",
                prompt=correction,
                history=tuple(_history_exchange(correction_old)),
                expected_topic_id=correction_new.concept_id,
                expect_resolved=True,
            )
        )

        corrected_history = _history_exchange(correction_old) + [
            {"role": "user", "text": correction},
            {"role": "assistant", "text": correction_new.summary},
        ]
        rows.append(
            MultiTurnCase(
                kind="correction_persists_to_followup",
                prompt=rng.choice(_FOLLOWUPS),
                history=tuple(corrected_history),
                expected_topic_id=correction_new.concept_id,
                expect_resolved=True,
            )
        )

        ack_history = _history_exchange(old) + [
            {"role": "user", "text": rng.choice(_ACKS)},
            {"role": "assistant", "text": "了解しました。"},
        ]
        rows.append(
            MultiTurnCase(
                kind="acknowledgement_keeps_topic",
                prompt=rng.choice(_FOLLOWUPS),
                history=tuple(ack_history),
                expected_topic_id=old.concept_id,
                expect_resolved=True,
            )
        )

    rng.shuffle(rows)
    return tuple(rows)
