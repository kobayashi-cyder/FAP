#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fap_v87_81_coding_conversation_gateway as latest


QUESTION_URL = "https://www.dnc.ac.jp/albums/abm.php?d=2144&f=abm00017558.pdf&n=2026_ol_10_reading.pdf"
ANSWER_URL = "https://www.dnc.ac.jp/albums/abm.php?d=2137&f=abm00006039.pdf&n=R8_%E3%80%90%E8%8B%B1%E8%AA%9E%EF%BC%88%E3%83%AA%E3%83%BC%E3%83%87%E3%82%A3%E3%83%B3%E3%82%B0%EF%BC%89%E3%80%91%E7%99%BA%E8%A1%A8%E7%94%A8%E6%AD%A3%E8%A7%A3.pdf"

# Official 2026 English Reading items that are single-answer, four-option,
# text-extractable tasks under the current FAP A-D benchmark interface.
ITEM_LOCATIONS = {
    1: (1, 0), 3: (1, 1),
    4: (3, 0), 5: (3, 1), 6: (3, 2), 7: (4, 0),
    8: (6, 0), 13: (6, 1),
    14: (8, 0), 15: (9, 0), 16: (9, 1), 17: (9, 2),
    18: (13, 0), 19: (13, 1), 21: (14, 0),
    30: (18, 0), 31: (19, 0),
    32: (23, 0), 35: (23, 1), 36: (23, 2),
    38: (26, 0), 39: (26, 1),
    43: (29, 0), 44: (30, 0),
}

POINTS = {
    1: 2, 3: 2,
    4: 3, 5: 3, 6: 3, 7: 3, 8: 3, 13: 3,
    14: 3, 15: 3, 16: 3, 17: 3, 18: 3, 19: 3, 21: 3,
    30: 3, 31: 3, 32: 3, 35: 3, 36: 3, 38: 3, 39: 3, 43: 3,
    44: 4,
}

SECTION_PAGES = {
    1: (0, 1), 3: (0, 1),
    4: (2, 4), 5: (2, 4), 6: (2, 4), 7: (2, 4),
    8: (5, 6), 13: (5, 6),
    14: (7, 9), 15: (7, 9), 16: (7, 9), 17: (7, 9),
    18: (10, 14), 19: (10, 14), 21: (10, 14),
    30: (15, 19), 31: (15, 19),
    32: (20, 24), 35: (20, 24), 36: (20, 24),
    38: (25, 30), 39: (25, 30), 43: (25, 30), 44: (25, 30),
}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def norm(text: str) -> str:
    text = re.sub(r"/c0\d{2}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def four_choice_blocks(text: str) -> list[tuple[str, list[str]]]:
    blocks = []
    pos = 0
    while True:
        s = text.find("/c033", pos)
        if s < 0:
            break
        next_q = text.find("\u0ef0", s + 1)
        end = len(text) if next_q < 0 else next_q
        segment = text[s:end]
        if all(f"/c03{x}" in segment for x in (3, 4, 5, 6)) and "/c037" not in segment:
            markers = [segment.find(f"/c03{x}") for x in (3, 4, 5, 6)]
            if markers == sorted(markers) and min(markers) >= 0:
                qstart = text.rfind("\u0ef0", 0, s)
                qtext = text[qstart:s] if qstart >= 0 else text[max(0, s - 300):s]
                choices = []
                for i, marker in enumerate(markers):
                    start = marker + 5
                    stop = markers[i + 1] if i < 3 else len(segment)
                    value = segment[start:stop]
                    value = re.split(r"[ʕ―ୈ]", value, maxsplit=1)[0]
                    choices.append(norm(value))
                if all(choices):
                    blocks.append((norm(qtext), choices))
        pos = s + 5
    return blocks


def parse_answers(text: str) -> dict[int, int]:
    targets = set(ITEM_LOCATIONS)
    answers: dict[int, int] = {}
    for line in text.splitlines():
        nums = [int(x) for x in re.findall(r"\d+", line)]
        if not nums:
            continue
        if len(nums) >= 2 and 1 <= nums[0] <= 21 and nums[0] in targets and nums[0] not in answers:
            answers[nums[0]] = nums[1]
        for i, value in enumerate(nums[:-1]):
            if value in targets and value > 21 and value not in answers:
                answers[value] = nums[i + 1]
    missing = sorted(targets - set(answers))
    if missing:
        raise RuntimeError(f"answer-key extraction missing items: {missing}")
    return answers


def answer_letter(result: dict) -> str:
    reply = str(result.get("reply") or "")
    matches = re.findall(r"(?im)^\s*Answer\s*:\s*\$?([A-D])\$?\s*$", reply)
    return matches[-1].upper() if matches else ""


def prompt(context: str, question: str, choices: list[str]) -> str:
    return "\n".join([
        "Answer the following multiple-choice question.",
        "Use the supplied official exam context. Return the final line exactly as: Answer: $LETTER",
        "",
        "Context:",
        context,
        "",
        "Target question:",
        question,
        "",
        *[f"{letter}) {choice}" for letter, choice in zip("ABCD", choices)],
    ])


def main() -> int:
    qbytes = download(QUESTION_URL)
    abytes = download(ANSWER_URL)
    qpdf = PdfReader(io.BytesIO(qbytes))
    apdf = PdfReader(io.BytesIO(abytes))
    pages = [page.extract_text() or "" for page in qpdf.pages]
    answers = parse_answers(apdf.pages[0].extract_text() or "")
    print("ANSWER_MAP " + json.dumps({str(k): answers[k] for k in sorted(answers)}, ensure_ascii=False))

    extracted: dict[int, tuple[str, list[str]]] = {}
    for item, (page_index, block_index) in ITEM_LOCATIONS.items():
        blocks = four_choice_blocks(pages[page_index])
        if block_index >= len(blocks):
            raise RuntimeError(
                f"item {item}: expected block {block_index} on page {page_index}, found {len(blocks)}"
            )
        extracted[item] = blocks[block_index]

    core = latest.FAPV8781Unified()
    details = []
    earned = 0
    available = sum(POINTS.values())

    for item in sorted(ITEM_LOCATIONS):
        question, choices = extracted[item]
        p0, p1 = SECTION_PAGES[item]
        context = norm(" ".join(pages[p0:p1 + 1]))
        sid = f"official-r8-reading-{item}"
        if hasattr(latest.base.MEMORY, "clear"):
            latest.base.MEMORY.clear(sid)
        if hasattr(core, "clear_route_continuity"):
            core.clear_route_continuity(sid)

        packed = prompt(context, question, choices)
        parsed = core.mcq_parser.parse(packed)
        print("PARSE_DIAG " + json.dumps({
            "item": item,
            "parsed": parsed is not None,
            "has_context": bool(parsed and "Context:" in parsed.question),
            "has_target": bool(parsed and "Target question:" in parsed.question),
            "question_chars": len(parsed.question) if parsed else 0,
            "question_tail": (parsed.question[-180:] if parsed else ""),
        }, ensure_ascii=False))
        result = core.chat(packed, sid)
        pred = answer_letter(result)
        expected = "ABCD"[answers[item] - 1]
        ok = pred == expected
        points = POINTS[item]
        if ok:
            earned += points
        else:
            try:
                diag = core.mcq_reasoner.reading_reasoner.diagnose(
                    core.mcq_parser.parse(packed).question,
                    core.mcq_parser.parse(packed).choices,
                )
                print("READING_FAIL_DIAG " + json.dumps({"item": item, **diag}, ensure_ascii=False))
            except Exception as exc:
                print("READING_FAIL_DIAG_ERROR", item, repr(exc))
        details.append({
            "item": item,
            "correct": ok,
            "predicted": pred or None,
            "points": points,
            "verdict": result.get("verdict"),
            "confidence": result.get("confidence"),
            "forced_choice": bool((result.get("structured_mcq") or {}).get("forced_choice", False)),
            "decision_source": (result.get("structured_mcq") or {}).get("decision_source"),
        })

    report = {
        "contract": "fap.official-common-test.r8.english-reading.text4.v1",
        "exam": "2026 (Reiwa 8) Common Test main examination",
        "subject": "English Reading",
        "official_total_points": 100,
        "evaluated_points": available,
        "excluded_points": 100 - available,
        "earned_points": earned,
        "evaluated_subset_percent": round(100 * earned / available, 3),
        "raw_exam_points_confirmed": earned,
        "question_pdf_sha256": hashlib.sha256(qbytes).hexdigest(),
        "answer_pdf_sha256": hashlib.sha256(abytes).hexdigest(),
        "items_evaluated": len(details),
        "items_correct": sum(int(d["correct"]) for d in details),
        "details": details,
    }
    out = ROOT / "runtime" / "official_r8_reading_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("ITEM_RESULTS " + json.dumps([
        {"item": d["item"], "correct": d["correct"], "predicted": d["predicted"], "verdict": d["verdict"], "confidence": d["confidence"], "forced_choice": d["forced_choice"]}
        for d in details
    ], ensure_ascii=False))
    print(json.dumps({
        "exam": report["exam"],
        "subject": report["subject"],
        "items": f'{report["items_correct"]}/{report["items_evaluated"]}',
        "earned_over_evaluated": f'{earned}/{available}',
        "evaluated_subset_percent": report["evaluated_subset_percent"],
        "confirmed_raw_exam_points": earned,
        "excluded_points": report["excluded_points"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
