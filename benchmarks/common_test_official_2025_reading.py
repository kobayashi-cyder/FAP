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

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import fap_v87_81_coding_conversation_gateway as latest

QUESTION_URL="https://www.dnc.ac.jp/albums/abm.php?d=771&f=abm00005957.pdf&n=2025_op_20_reading.pdf"
ANSWER_URL="https://www.dnc.ac.jp/albums/abm.php?d=740&f=abm00005150.pdf&n=R7_%E3%80%90%E8%8B%B1%E8%AA%9E%EF%BC%88%E3%83%AA%E3%83%BC%E3%83%87%E3%82%A3%E3%83%B3%E3%82%B0%EF%BC%89%E3%80%91%E6%9C%AC%E8%A9%A6%E9%A8%93%E3%81%AE%E6%AD%A3%E8%A7%A3.pdf"

ITEM_LOCATIONS={
    1:(1,0),2:(1,1),
    4:(4,0),5:(4,1),6:(5,0),7:(5,1),
    8:(7,0),13:(7,1),
    14:(9,0),15:(9,1),16:(10,0),17:(10,1),
    18:(14,0),21:(14,1),
    29:(20,1),
    32:(24,0),36:(25,0),37:(25,1),
    38:(27,0),39:(27,1),43:(31,0),44:(31,1),
}
POINTS={
    1:2,2:2,
    4:3,5:3,6:3,7:3,
    8:3,13:3,
    14:3,15:3,16:3,17:3,
    18:3,21:3,
    29:3,
    32:3,36:3,37:3,
    38:3,39:3,43:3,44:4,
}
SECTION_PAGES={
    1:(0,1),2:(0,1),
    4:(3,5),5:(3,5),6:(3,5),7:(3,5),
    8:(6,7),13:(6,7),
    14:(8,10),15:(8,10),16:(8,10),17:(8,10),
    18:(11,14),21:(11,14),
    29:(16,20),
    32:(21,25),36:(21,25),37:(21,25),
    38:(26,31),39:(26,31),43:(26,31),44:(26,31),
}

def download(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read()

def norm(text):
    text=re.sub(r"/c0\d{2}"," ",str(text or ""))
    return re.sub(r"\s+"," ",text).strip()

def four_choice_blocks(text):
    out=[]; pos=0
    while True:
        s=text.find("/c033",pos)
        if s<0: break
        n=text.find("\u0ef0",s+1)
        e=len(text) if n<0 else n
        seg=text[s:e]
        if all(f"/c03{x}" in seg for x in (3,4,5,6)) and "/c037" not in seg:
            marks=[seg.find(f"/c03{x}") for x in (3,4,5,6)]
            if marks==sorted(marks) and min(marks)>=0:
                qstart=text.rfind("\u0ef0",0,s)
                qtext=text[qstart:s] if qstart>=0 else text[max(0,s-300):s]
                choices=[]
                for i,m in enumerate(marks):
                    start=m+5; stop=marks[i+1] if i<3 else len(seg)
                    value=re.split(r"[ʕ―ୈ]",seg[start:stop],maxsplit=1)[0]
                    choices.append(norm(value))
                if all(choices):
                    out.append((norm(qtext),choices))
        pos=s+5
    return out

def parse_answers(text):
    targets=set(ITEM_LOCATIONS)
    answers={}
    for line in text.splitlines():
        nums=[int(x) for x in re.findall(r"\d+",line)]
        if len(nums)>=2 and nums[0] in targets and nums[0] not in answers:
            answers[nums[0]]=nums[1]
        for i,value in enumerate(nums[:-1]):
            if value in targets and value>23 and value not in answers:
                answers[value]=nums[i+1]
    missing=sorted(targets-set(answers))
    if missing: raise RuntimeError(f"missing answer keys: {missing}")
    return answers

def answer_letter(result):
    m=re.findall(r"(?im)^\s*Answer\s*:\s*\$?([A-D])\$?\s*$",str(result.get("reply") or ""))
    return m[-1].upper() if m else ""

def pack(context,question,choices):
    return "\n".join([
        "Answer the following multiple-choice question.",
        "Use the supplied official exam context. Return the final line exactly as: Answer: $LETTER",
        "","Context:",context,"","Target question:",question,"",
        *[f"{l}) {v}" for l,v in zip("ABCD",choices)]
    ])

def main():
    qb=download(QUESTION_URL); ab=download(ANSWER_URL)
    q=PdfReader(io.BytesIO(qb)); a=PdfReader(io.BytesIO(ab))
    pages=[p.extract_text() or "" for p in q.pages]
    answers=parse_answers(a.pages[0].extract_text() or "")
    print("ANSWER_MAP "+json.dumps({str(k):answers[k] for k in sorted(answers)}))

    extracted={}
    for item,(page,idx) in ITEM_LOCATIONS.items():
        blocks=four_choice_blocks(pages[page])
        if idx>=len(blocks):
            raise RuntimeError(f"item {item}: page={page} idx={idx} blocks={len(blocks)}")
        extracted[item]=blocks[idx]

    core=latest.FAPV8781Unified()
    earned=0; details=[]
    for item in sorted(ITEM_LOCATIONS):
        question,choices=extracted[item]
        p0,p1=SECTION_PAGES[item]
        context=norm(" ".join(pages[p0:p1+1]))
        sid=f"official-r7-reading-{item}"
        if hasattr(latest.base.MEMORY,"clear"): latest.base.MEMORY.clear(sid)
        if hasattr(core,"clear_route_continuity"): core.clear_route_continuity(sid)
        result=core.chat(pack(context,question,choices),sid)
        pred=answer_letter(result)
        expected="ABCD"[answers[item]-1]
        ok=pred==expected
        if ok:
            earned+=POINTS[item]
        else:
            try:
                parsed=core.mcq_parser.parse(pack(context,question,choices))
                diag=core.mcq_reasoner.reading_reasoner.diagnose(parsed.question,parsed.choices)
                print("R7_FAIL_DIAG "+json.dumps({"item":item,**diag},ensure_ascii=False))
            except Exception as exc:
                print("R7_FAIL_DIAG_ERROR",item,repr(exc))
        details.append({"item":item,"correct":ok,"predicted":pred or None,"points":POINTS[item],
                        "verdict":result.get("verdict"),"confidence":result.get("confidence"),
                        "decision_source":(result.get("structured_mcq") or {}).get("decision_source")})
    available=sum(POINTS.values())
    report={
        "contract":"fap.official-common-test.r7.english-reading.text4.v1",
        "exam":"2025 (Reiwa 7) Common Test main examination",
        "subject":"English Reading",
        "official_total_points":100,
        "evaluated_points":available,
        "excluded_points":100-available,
        "earned_points":earned,
        "evaluated_subset_percent":round(100*earned/available,3),
        "raw_exam_points_confirmed":earned,
        "items_evaluated":len(details),
        "items_correct":sum(int(d["correct"]) for d in details),
        "question_pdf_sha256":hashlib.sha256(qb).hexdigest(),
        "answer_pdf_sha256":hashlib.sha256(ab).hexdigest(),
        "details":details,
    }
    out=ROOT/"runtime"/"official_r7_reading_report.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ITEM_RESULTS "+json.dumps(details,ensure_ascii=False))
    print(json.dumps({"exam":report["exam"],"items":f'{report["items_correct"]}/{report["items_evaluated"]}',
                      "earned_over_evaluated":f'{earned}/{available}',
                      "evaluated_subset_percent":report["evaluated_subset_percent"],
                      "confirmed_raw_exam_points":earned,"excluded_points":report["excluded_points"]},
                     ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
