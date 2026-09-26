#!/usr/bin/env python3
from __future__ import annotations

import csv, io, json, random, re, statistics, sys, time, urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fap_v87_26_scientific_reasoning_gateway as fap

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
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))

def main():
    rows = load_rows()
    rng = random.Random(0)
    prepared = []
    for row in rows * 4:
        base = [row["Correct Answer"], row["Incorrect Answer 1"], row["Incorrect Answer 2"], row["Incorrect Answer 3"]]
        choices = [base[i] for i in rng.sample(range(4), 4)]
        prepared.append((row, choices, "ABCD"[choices.index(row["Correct Answer"])]))

    scores, latencies = [], []
    parsed = 0
    sources, abilities, domains = Counter(), Counter(), Counter()
    evidence_decisions = 0
    for i, (row, choices, correct) in enumerate(prepared):
        prompt = TEMPLATE.format(Question=row["Question"], A=choices[0], B=choices[1], C=choices[2], D=choices[3])
        t0 = time.perf_counter()
        result = fap.CORE.chat(prompt, f"gpqa-v8726-{i:04d}")
        latencies.append(time.perf_counter() - t0)
        m = ANSWER_RE.search(str(result.get("reply", "")))
        pred = m.group(1).upper() if m else None
        parsed += int(pred is not None)
        scores.append(int(pred == correct))
        abilities[str(result.get("ability"))] += 1
        meta = result.get("structured_mcq") or {}
        src = str(meta.get("decision_source"))
        sources[src] += 1
        domains[str(meta.get("domain"))] += 1
        evidence_decisions += int(src == "option_conditioned_science")

    n = len(scores)
    summary = {
        "benchmark": "GPQA Diamond",
        "harness": "OpenAI simple-evals compatible prompt/permutation/extraction",
        "fap_version": "87.26-scientific-reasoning",
        "teacher_fallback": False,
        "questions": len(rows),
        "repeats": 4,
        "trials": n,
        "correct": sum(scores),
        "accuracy": sum(scores) / n if n else 0.0,
        "parse_rate": parsed / n if n else 0.0,
        "evidence_decisions": evidence_decisions,
        "abilities": dict(abilities),
        "decision_sources": dict(sources),
        "domains": dict(domains),
        "median_latency_s": statistics.median(latencies) if latencies else 0.0,
        "mean_latency_s": statistics.mean(latencies) if latencies else 0.0,
    }
    (OUT / "gpqa_v8726_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
