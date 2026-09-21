#!/usr/bin/env python3
from __future__ import annotations

import csv, io, json, random, re, statistics, sys, time, urllib.request, hashlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fap_v87_26_scientific_reasoning_gateway as baseline
BASELINE_CORE = baseline.FAPV8726()
import fap_v87_27_physics_knowledge_gateway as candidate
CANDIDATE_CORE = candidate.CORE

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

def pred(core, prompt, sid):
    out = core.chat(prompt, sid)
    m = ANSWER_RE.search(str(out.get("reply","")))
    return (m.group(1).upper() if m else None), out

STOP = {"which","what","when","where","there","their","about","from","with","that","this","into","does","would","could","following","statement","correct","most","likely","given","have","has","been","were","will","than","then","only","each","between","under","using","such","these","those","because","while","whose","respect","system","systems"}

def split_of(question):
    return "dev" if hashlib.sha256(question.encode("utf-8")).digest()[0] % 2 == 0 else "holdout"

def topic_terms(question):
    words=[w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9+\-]{2,}", question)]
    return [w for w in words if w not in STOP]

def main():
    rows = load_rows()
    rng = random.Random(0)
    prepared = []
    for row in rows * 4:
        base = [row["Correct Answer"], row["Incorrect Answer 1"], row["Incorrect Answer 2"], row["Incorrect Answer 3"]]
        choices = [base[i] for i in rng.sample(range(4), 4)]
        prepared.append((row, choices, "ABCD"[choices.index(row["Correct Answer"])]))

    total = len(prepared)
    base_correct = cand_correct = parse = 0
    physics_total = physics_base = physics_cand = 0
    split_stats = {
        "dev": Counter(),
        "holdout": Counter(),
    }
    dev_physics_terms = Counter()
    changed = changed_to_correct = changed_to_wrong = 0
    sources = Counter()
    physics_used = 0
    latencies = []

    for i,(row,choices,correct) in enumerate(prepared):
        prompt = TEMPLATE.format(Question=row["Question"],A=choices[0],B=choices[1],C=choices[2],D=choices[3])
        bpred,bout = pred(BASELINE_CORE,prompt,f"v26-{i}")
        t0=time.perf_counter()
        cpred,cout = pred(CANDIDATE_CORE,prompt,f"v27-{i}")
        latencies.append(time.perf_counter()-t0)

        base_correct += int(bpred == correct)
        cand_correct += int(cpred == correct)
        parse += int(cpred is not None)

        meta = cout.get("structured_mcq") or {}
        domain = str(meta.get("domain"))
        src = str(meta.get("decision_source"))
        sources[src]+=1
        pk = meta.get("physics_knowledge") or {}
        physics_used += int(bool(pk.get("used")))

        split = split_of(row["Question"])
        split_stats[split]["trials"] += 1
        split_stats[split]["base_correct"] += int(bpred == correct)
        split_stats[split]["cand_correct"] += int(cpred == correct)

        if domain == "physics":
            physics_total += 1
            physics_base += int(bpred == correct)
            physics_cand += int(cpred == correct)
            split_stats[split]["physics_trials"] += 1
            split_stats[split]["physics_base_correct"] += int(bpred == correct)
            split_stats[split]["physics_cand_correct"] += int(cpred == correct)
            split_stats[split]["physics_used"] += int(bool(pk.get("used")))
            if split == "dev":
                dev_physics_terms.update(topic_terms(row["Question"]))

        if bpred != cpred:
            changed += 1
            if cpred == correct and bpred != correct: changed_to_correct += 1
            if bpred == correct and cpred != correct: changed_to_wrong += 1

    summary = {
      "benchmark":"GPQA Diamond",
      "trials":total,
      "v87_26_correct":base_correct,
      "v87_26_accuracy":base_correct/total,
      "v87_27_correct":cand_correct,
      "v87_27_accuracy":cand_correct/total,
      "delta_correct":cand_correct-base_correct,
      "parse_rate":parse/total,
      "physics_subset_trials":physics_total,
      "physics_v87_26_correct":physics_base,
      "physics_v87_26_accuracy":physics_base/physics_total if physics_total else 0,
      "physics_v87_27_correct":physics_cand,
      "physics_v87_27_accuracy":physics_cand/physics_total if physics_total else 0,
      "physics_delta_correct":physics_cand-physics_base,
      "physics_knowledge_used":physics_used,
      "changed_predictions":changed,
      "changed_to_correct":changed_to_correct,
      "changed_to_wrong":changed_to_wrong,
      "decision_sources":dict(sources),
      "split_stats": {
        name: {
          **dict(stats),
          "accuracy_base": stats["base_correct"]/stats["trials"] if stats["trials"] else 0,
          "accuracy_candidate": stats["cand_correct"]/stats["trials"] if stats["trials"] else 0,
          "physics_accuracy_base": stats["physics_base_correct"]/stats["physics_trials"] if stats["physics_trials"] else 0,
          "physics_accuracy_candidate": stats["physics_cand_correct"]/stats["physics_trials"] if stats["physics_trials"] else 0,
        }
        for name,stats in split_stats.items()
      },
      "dev_physics_topic_terms": dev_physics_terms.most_common(60),
      "median_latency_s":statistics.median(latencies),
      "mean_latency_s":statistics.mean(latencies),
    }
    (OUT/"gpqa_v8727_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
