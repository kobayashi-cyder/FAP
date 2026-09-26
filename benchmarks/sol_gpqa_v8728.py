#!/usr/bin/env python3
from __future__ import annotations

import csv, io, json, random, re, statistics, sys, time, urllib.request
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import fap_v87_27_physics_knowledge_gateway as v27
BASELINE=v27.FAPV8727()
import fap_v87_28_physics_solver_gateway as v28
CANDIDATE=v28.CORE

URL="https://openaipublic.blob.core.windows.net/simple-evals/gpqa_diamond.csv"
ANSWER_RE=re.compile(r"(?i)Answer[ \t]*:[ \t]*\$?([A-D])\$?")
OUT=Path("benchmark_results"); OUT.mkdir(exist_ok=True)
TEMPLATE="""Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' (without quotes) where LETTER is one of ABCD. Think step by step before answering.

{Question}

A) {A}
B) {B}
C) {C}
D) {D}"""

def load_rows():
    with urllib.request.urlopen(URL,timeout=30) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))

def run(core,prompt,sid):
    out=core.chat(prompt,sid)
    m=ANSWER_RE.search(str(out.get("reply","")))
    return (m.group(1).upper() if m else None),out

def main():
    rows=load_rows()
    rng=random.Random(0)
    prepared=[]
    for row in rows*4:
        base=[row["Correct Answer"],row["Incorrect Answer 1"],row["Incorrect Answer 2"],row["Incorrect Answer 3"]]
        choices=[base[i] for i in rng.sample(range(4),4)]
        correct="ABCD"[choices.index(row["Correct Answer"])]
        prepared.append((row,choices,correct))

    base_correct=cand_correct=parsed=0
    changed=to_correct=to_wrong=0
    solver_counts=Counter()
    lat=[]
    for i,(row,choices,correct) in enumerate(prepared):
        prompt=TEMPLATE.format(Question=row["Question"],A=choices[0],B=choices[1],C=choices[2],D=choices[3])
        bp,_=run(BASELINE,prompt,f"v27-{i}")
        t0=time.perf_counter()
        cp,out=run(CANDIDATE,prompt,f"v28-{i}")
        lat.append(time.perf_counter()-t0)
        base_correct+=int(bp==correct); cand_correct+=int(cp==correct); parsed+=int(cp is not None)
        if bp!=cp:
            changed+=1
            to_correct+=int(cp==correct and bp!=correct)
            to_wrong+=int(bp==correct and cp!=correct)
        meta=out.get("structured_mcq") or {}
        det=meta.get("physics_deterministic") or {}
        if det.get("used"):
            solver_counts[str(det.get("solver"))]+=1

    n=len(prepared)
    summary={
      "benchmark":"GPQA Diamond",
      "trials":n,
      "v87_27_correct":base_correct,
      "v87_27_accuracy":base_correct/n,
      "v87_28_correct":cand_correct,
      "v87_28_accuracy":cand_correct/n,
      "delta_correct":cand_correct-base_correct,
      "parse_rate":parsed/n,
      "changed_predictions":changed,
      "changed_to_correct":to_correct,
      "changed_to_wrong":to_wrong,
      "v87_28_solver_counts":dict(solver_counts),
      "median_latency_s":statistics.median(lat),
      "mean_latency_s":statistics.mean(lat),
    }
    (OUT/"gpqa_v8728_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
