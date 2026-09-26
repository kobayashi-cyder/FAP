#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fap_v87_81_coding_conversation_gateway as latest


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: object required")
        rows.append(row)
    return rows


def _index_answers(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        item_id = str(row.get("item_id") or "").strip()
        answer = str(row.get("answer") or "").strip().upper()
        if not item_id or answer not in {"A", "B", "C", "D"}:
            raise ValueError("answer rows require item_id and answer A-D")
        if item_id in out:
            raise ValueError(f"duplicate answer item_id: {item_id}")
        out[item_id] = answer
    return out


def _prompt(row: dict[str, Any]) -> str:
    question = str(row.get("question") or "").strip()
    choices = row.get("choices")
    if not question or not isinstance(choices, dict):
        raise ValueError("question rows require question and choices")
    normalized = {str(k).upper(): str(v) for k, v in choices.items()}
    if set(normalized) != {"A", "B", "C", "D"}:
        raise ValueError("choices must contain exactly A-D")
    return "\n".join([
        "Answer the following multiple-choice question.",
        "Return the final line exactly as: Answer: $LETTER",
        "",
        question,
        "",
        *[f"{letter}) {normalized[letter]}" for letter in "ABCD"],
    ])


def _answer_letter(result: dict[str, Any]) -> str:
    import re
    reply = str(result.get("reply") or "")
    matches = re.findall(r"(?im)^\s*Answer\s*:\s*\$?([A-D])\$?\s*$", reply)
    return matches[-1].upper() if matches else ""


def evaluate(question_path: Path, answer_path: Path) -> dict[str, Any]:
    questions = _read_jsonl(question_path)
    answers = _index_answers(_read_jsonl(answer_path))
    core = latest.FAPV8781Unified()

    by_subject = defaultdict(lambda: {"total": 0, "correct": 0})
    details = []
    correct = 0

    for index, row in enumerate(questions):
        item_id = str(row.get("item_id") or "").strip()
        subject = str(row.get("subject") or "unknown").strip() or "unknown"
        if not item_id:
            raise ValueError(f"question row {index} missing item_id")
        if item_id not in answers:
            raise ValueError(f"missing answer key for {item_id}")

        sid = f"common-test-{item_id}"
        if hasattr(latest.base.MEMORY, "clear"):
            latest.base.MEMORY.clear(sid)
        if hasattr(core, "clear_route_continuity"):
            core.clear_route_continuity(sid)

        result = core.chat(_prompt(row), sid)
        predicted = _answer_letter(result)
        expected = answers[item_id]
        ok = predicted == expected
        correct += int(ok)
        by_subject[subject]["total"] += 1
        by_subject[subject]["correct"] += int(ok)

        details.append({
            "item_id": item_id,
            "subject": subject,
            "correct": ok,
            "predicted": predicted or None,
            "verdict": result.get("verdict"),
            "confidence": result.get("confidence"),
            "forced_choice": bool((result.get("structured_mcq") or {}).get("forced_choice", False)),
        })

    total = len(questions)
    report = {
        "contract": "fap.common-test-benchmark.v1",
        "dataset_id": str(questions[0].get("dataset_id") if questions else "empty"),
        "total": total,
        "correct": correct,
        "score_percent": round(100.0 * correct / total, 3) if total else 0.0,
        "subjects": {
            subject: {
                **stats,
                "score_percent": round(100.0 * stats["correct"] / stats["total"], 3),
            }
            for subject, stats in sorted(by_subject.items())
        },
        "answer_key_sha256": hashlib.sha256(answer_path.read_bytes()).hexdigest(),
        "questions_sha256": hashlib.sha256(question_path.read_bytes()).hexdigest(),
        "details": details,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True)
    parser.add_argument("--answers", required=True)
    parser.add_argument("--output", default="runtime/common_test_report.json")
    args = parser.parse_args()

    report = evaluate(Path(args.questions), Path(args.answers))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "dataset_id": report["dataset_id"],
        "total": report["total"],
        "correct": report["correct"],
        "score_percent": report["score_percent"],
        "subjects": report["subjects"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
