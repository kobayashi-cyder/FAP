#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


SUBJECTS = (
    "mathematics",
    "physics",
    "chemistry",
    "biology",
    "information",
    "english_reading",
)


def _item(subject: str, index: int, rng: random.Random) -> tuple[dict, dict]:
    item_id = f"synthetic-{subject}-{index:03d}"

    if subject == "mathematics":
        a, b, c = rng.randint(2, 9), rng.randint(3, 15), rng.randint(2, 8)
        value = a * b + c
        question = f"A value is multiplied: {a} × {b}, then {c} is added. What is the result?"
        options = [value, value + 1, value - 1, a + b + c]
    elif subject == "physics":
        v, t = rng.randint(2, 18), rng.randint(2, 12)
        value = v * t
        question = f"An object moves at constant speed {v} m/s for {t} s. How far does it travel in metres?"
        options = [value, v + t, value + v, max(1, value - t)]
    elif subject == "chemistry":
        n, m = rng.randint(2, 8), rng.randint(2, 10)
        value = n * m
        question = f"A sample contains {n} groups with {m} particles in each group. How many particles are represented?"
        options = [value, n + m, value + 1, max(1, value - 1)]
    elif subject == "biology":
        total = rng.choice([20, 40, 60, 80])
        pct = rng.choice([25, 50, 75])
        value = total * pct // 100
        question = f"In a population of {total} cells, {pct}% show a marker. How many cells show the marker?"
        options = [value, total - value, pct, total]
    elif subject == "information":
        start = rng.randint(2, 9)
        loops = rng.randint(2, 6)
        inc = rng.randint(1, 5)
        value = start + loops * inc
        question = (
            f"A variable starts at {start}. A loop runs {loops} times and adds {inc} "
            "each time. What is the final value?"
        )
        options = [value, start + inc, loops * inc, value + inc]
    else:
        subject_word = rng.choice(["archive", "laboratory", "station", "library"])
        question = (
            f"A notice says: 'The {subject_word} opens at 9:00 and closes at 17:00. "
            "Visitors arriving after 16:30 may not enter.' Which statement follows?"
        )
        options = [
            "A visitor arriving at 16:45 may be refused entry.",
            "The facility closes at 16:30.",
            "All visitors must arrive before 9:00.",
            "The facility is open overnight.",
        ]

    unique = []
    for value in options:
        text = str(value)
        if text not in unique:
            unique.append(text)
    bump = 1
    while len(unique) < 4:
        candidate = str(int(unique[0]) + bump) if unique[0].lstrip("-").isdigit() else f"distractor-{bump}"
        if candidate not in unique:
            unique.append(candidate)
        bump += 1

    indexed = list(enumerate(unique[:4]))
    rng.shuffle(indexed)
    choices = {}
    answer = ""
    for letter, (original, text) in zip("ABCD", indexed):
        choices[letter] = text
        if original == 0:
            answer = letter

    qrow = {
        "dataset_id": "fap-common-test-style-synthetic-v1",
        "item_id": item_id,
        "subject": subject,
        "question": question,
        "choices": choices,
    }
    arow = {"item_id": item_id, "answer": answer}
    return qrow, arow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260926)
    parser.add_argument("--per-subject", type=int, default=4)
    parser.add_argument("--questions", default="runtime/common_test_synthetic_questions.jsonl")
    parser.add_argument("--answers", default="runtime/common_test_synthetic_answers.jsonl")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    qrows, arows = [], []
    for subject in SUBJECTS:
        for index in range(args.per_subject):
            q, a = _item(subject, index, rng)
            qrows.append(q)
            arows.append(a)

    qpath, apath = Path(args.questions), Path(args.answers)
    qpath.parent.mkdir(parents=True, exist_ok=True)
    apath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in qrows) + "\n", encoding="utf-8")
    apath.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in arows) + "\n", encoding="utf-8")
    print(f"generated {len(qrows)} items across {len(SUBJECTS)} subjects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
