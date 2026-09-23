#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unicodedata
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fap_v87_81_coding_conversation_gateway as gateway
from fap_pdf_document import PDFDocumentIngestor
from fap_information_reasoner import InformationFundamentalsReasoner

PDF_URL = "https://www.dnc.ac.jp/albums/abm.php?d=2144&f=abm00017564.pdf&n=2026_ol_27_joho1.pdf"

SECTIONS = [
    {"name":"第1問","pages":(1,8),"points":20,"groups":[
        (["ア","イ"],["0","3"],2,False),(["ウ"],["3"],2,False),
        (["エ","オ"],["e","4"],2,False),(["カ","キ","ク","ケ"],["9","6","6","9"],4,False),
        (["コ"],["0"],2,False),(["サ"],["3"],2,False),(["シ"],["5"],1,False),
        (["ス"],["2"],2,False),(["セ"],["2"],2,False),(["ソ"],["0"],1,False)]},
    {"name":"第2問","pages":(9,20),"points":30,"groups":[
        (["ア","イ"],["2","4"],3,True),(["ウ","エ","オ"],["4","8","1"],3,False),
        (["カ"],["2"],2,False),(["キ"],["1"],2,False),(["ク"],["5"],2,False),
        (["ケ"],["2"],3,False),(["コ"],["7"],1,False),(["サ"],["3"],1,False),
        (["シ"],["0"],3,False),(["ス"],["2"],3,False),(["セ","ソ"],["3","5"],2,False),
        (["タ"],["0"],3,False),(["チ"],["0"],2,False)]},
    {"name":"第3問","pages":(21,26),"points":25,"groups":[
        (["ア","イ","ウ"],["9","2","4"],3,False),(["エ"],["3"],1,False),(["オ"],["0"],1,False),
        (["カ"],["1"],2,False),(["キ"],["2"],2,False),(["ク"],["5"],2,False),
        (["ケ"],["2"],2,False),(["コ"],["2"],2,False),(["サ"],["3"],2,False),
        (["シ"],["2"],2,False),(["ス"],["0"],2,False),(["セ"],["2"],2,False),(["ソ"],["5"],2,False)]},
    {"name":"第4問","pages":(27,34),"points":25,"groups":[
        (["ア"],["1"],2,False),(["イ"],["3"],1,False),(["ウ"],["2"],2,False),
        (["エ","オ"],["2","5"],2,False),(["カ"],["3"],2,False),(["キ"],["1"],2,False),
        (["ク"],["4"],2,False),(["ケ"],["2"],2,False),(["コ"],["0"],2,False),
        (["サ"],["3"],3,False),(["シ"],["2"],3,False),(["ス"],["1"],2,False)]},
]

def norm(v: object) -> str:
    s = unicodedata.normalize("NFKC", str(v or "")).strip().lower()
    return re.sub(r"\s+", "", s)

def download_pdf(path: Path) -> None:
    req = urllib.request.Request(PDF_URL, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        path.write_bytes(r.read())

def extract_pages(pdf: Path, first: int, last: int) -> str:
    p = subprocess.run(
        ["pdftotext","-layout","-enc","UTF-8","-f",str(first),"-l",str(last),str(pdf),"-"],
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return p.stdout

def prompt_for(section: dict, body: str) -> str:
    symbols = []
    for syms, _, _, _ in section["groups"]:
        for s in syms:
            if s not in symbols:
                symbols.append(s)
    return (
        "これは令和8年度大学入学共通テスト『情報I』の" + section["name"] + "です。"
        "問題本文だけを根拠に解いてください。解説は書かず、各解答記号の答えをJSONオブジェクトだけで返してください。"
        "選択肢は問題冊子に示されたマーク番号を0から始まる数字として返してください。"
        "16進数の文字指定はその文字を返してください。キーは次のみです: "
        + ",".join(symbols) + "\n\n" + body
    )

def parse_answer(reply: str) -> dict[str,str]:
    for raw in reversed(re.findall(r"\{[\s\S]*?\}", reply or "")):
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict):
            return {str(k):norm(v) for k,v in obj.items()}
    return {}

def score_section(section: dict, pred: dict[str,str]):
    score = 0
    details = []
    for syms, answers, points, unordered in section["groups"]:
        got = [pred.get(s,"") for s in syms]
        exp = [norm(a) for a in answers]
        ok = sorted(got) == sorted(exp) if unordered else got == exp
        if ok:
            score += points
        details.append({"symbols":syms,"expected":exp,"predicted":got,"points":points,"correct":ok})
    return score, details

def main() -> None:
    out_dir = Path("benchmark_results")
    out_dir.mkdir(exist_ok=True)
    total = 0
    results = []
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "info1.pdf"
        download_pdf(pdf)
        core = gateway.FAPV8781Unified()
        document = PDFDocumentIngestor(render_images=False).read(pdf)
        info_reasoner = InformationFundamentalsReasoner()
        print("pdf_pages:", document.page_count)
        for idx, section in enumerate(SECTIONS, start=1):
            body = document.text_for_pages(*section["pages"])
            prompt = prompt_for(section, body)
            deterministic, rule_evidence = info_reasoner.solve(body)
            response = core.chat(prompt, "common-test-2026-info1-" + str(idx))
            reply = str(response.get("reply") or "")
            pred = parse_answer(reply)
            pred.update(deterministic)
            score, details = score_section(section, pred)
            print("rule_answers:", json.dumps(deterministic, ensure_ascii=False))
            print("rule_evidence:", json.dumps([e.__dict__ for e in rule_evidence], ensure_ascii=False))
            total += score
            results.append({
                "section":section["name"],"score":score,"max_score":section["points"],
                "route":response.get("route",[]),"verdict":response.get("verdict",""),
                "reply":reply,"parsed":pred,"details":details
            })
            print(section["name"] + ": " + str(score) + "/" + str(section["points"]))
            print("reply:", reply[:1000].replace("\n"," "))
    payload = {
        "benchmark":"2026 Common Test Information I",
        "fap_version":gateway.VERSION,
        "score":total,"max_score":100,"percent":total,
        "input_mode":"FAP PDFDocumentIngestor page-aware local PDF ingestion; page images are supported but not yet used by the answer reasoner",
        "source_pdf":PDF_URL,"sections":results
    }
    (out_dir/"common_test_2026_info1.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    md = [
        "# FAP 2026 Common Test - Information I","",
        "- FAP: " + gateway.VERSION,
        "- Score: **" + str(total) + "/100**",
        "- Input mode: FAP PDFDocumentIngestor (page-aware local PDF ingestion).","",
        "| Section | Score |","|---|---:|"
    ]
    for row in results:
        md.append("| " + row["section"] + " | " + str(row["score"]) + "/" + str(row["max_score"]) + " |")
    md += ["","Raw model replies and item-level grading are in the JSON artifact."]
    (out_dir/"common_test_2026_info1.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print("TOTAL: " + str(total) + "/100")

if __name__ == "__main__":
    main()
