#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import random
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fap_v87_25_structured_reasoning_gateway as fap

# Public dataset used by OpenAI simple-evals. No answer table is embedded here.
BENCHMARK_REVISION = "v87.25-1"
URL = "https://openaipublic.blob.core.windows.net/simple-evals/gpqa_diamond.csv"
ANSWER_RE = re.compile(r"(?i)Answer[ \t]*:[ \t]*\$?([A-D])\$?")
OUT = Path("benchmark_results")
OUT.mkdir(exist_ok=True)

TEMPLATE = """Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' (without quotes) where LETTER is one of ABCD. Think step by step before answering.

{Question}

A) {A}
B) {B}
C) {C}
D) {D}"""


def load_rows():
    with urllib.request.urlopen(URL, timeout=30) as r:
        text = r.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def main():
    rows = load_rows()
    rng = random.Random(0)
    prepared = []
    for row in rows * 4:
        base = [
            row["Correct Answer"],
            row["Incorrect Answer 1"],
            row["Incorrect Answer 2"],
            row["Incorrect Answer 3"],
        ]
        choices = [base[i] for i in rng.sample(range(4), 4)]
        correct = "ABCD"[choices.index(row["Correct Answer"])]
        prepared.append((row, choices, correct))

    scores = []
    latencies = []
    parsed = 0
    sources = Counter()
    abilities = Counter()

    for i, (row, choices, correct) in enumerate(prepared):
        prompt = TEMPLATE.format(
            Question=row["Question"],
            A=choices[0], B=choices[1], C=choices[2], D=choices[3],
        )
        t0 = time.perf_counter()
        result = fap.CORE.chat(prompt, f"gpqa-v8725-{i:04d}")
        latencies.append(time.perf_counter() - t0)
        reply = str(result.get("reply", ""))
        m = ANSWER_RE.search(reply)
        pred = m.group(1).upper() if m else None
        parsed += int(pred is not None)
        scores.append(int(pred == correct))
        abilities[str(result.get("ability"))] += 1
        meta = result.get("structured_mcq") or {}
        sources[str(meta.get("decision_source"))] += 1

    n = len(scores)
    summary = {
        "benchmark": "GPQA Diamond",
        "harness": "OpenAI simple-evals compatible prompt/permutation/extraction",
        "fap_version": "87.25-structured-reasoning",
        "teacher_fallback": False,
        "questions": len(rows),
        "repeats": 4,
        "trials": n,
        "correct": sum(scores),
        "accuracy": sum(scores) / n if n else 0.0,
        "parse_rate": parsed / n if n else 0.0,
        "abilities": dict(abilities),
        "decision_sources": dict(sources),
        "median_latency_s": statistics.median(latencies) if latencies else 0.0,
        "mean_latency_s": statistics.mean(latencies) if latencies else 0.0,
    }
    (OUT / "gpqa_v8725_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
