#!/usr/bin/env python3
from __future__ import annotations
import io, re, urllib.request
from pypdf import PdfReader

Q_URL="https://www.dnc.ac.jp/albums/abm.php?d=771&f=abm00005957.pdf&n=2025_op_20_reading.pdf"
A_URL="https://www.dnc.ac.jp/albums/abm.php?d=740&f=abm00005150.pdf&n=R7_%E3%80%90%E8%8B%B1%E8%AA%9E%EF%BC%88%E3%83%AA%E3%83%BC%E3%83%87%E3%82%A3%E3%83%B3%E3%82%B0%EF%BC%89%E3%80%91%E6%9C%AC%E8%A9%A6%E9%A8%93%E3%81%AE%E6%AD%A3%E8%A7%A3.pdf"

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read()

q=PdfReader(io.BytesIO(get(Q_URL)))
a=PdfReader(io.BytesIO(get(A_URL)))
print("PAGES",len(q.pages),len(a.pages))
for i in [0,1,3,4,6,7,8,9,12,15,20,25,30]:
    if i<len(q.pages):
        t=q.pages[i].extract_text() or ""
        print("PAGE",i,"LEN",len(t),"CTRL",sorted({ord(ch) for ch in t if ord(ch)<32 and ch not in "\n\t\r"}))
        print("HEAD",repr(re.sub(r"\s+"," ",t[:900])))
print("ANS",repr((a.pages[0].extract_text() or "")[:3500]))

print("FOUR_CHOICE_BLOCKS")
for pi,page in enumerate(q.pages):
    t=page.extract_text() or ""
    pos=0
    bi=0
    while True:
        s=t.find("/c033",pos)
        if s<0: break
        n=t.find("\u0ef0",s+1)
        e=len(t) if n<0 else n
        seg=t[s:e]
        if all(f"/c03{x}" in seg for x in [3,4,5,6]) and "/c037" not in seg:
            qs=t.rfind("\u0ef0",0,s)
            qtxt=t[qs:s] if qs>=0 else t[max(0,s-240):s]
            print("P",pi,"B",bi,"Q",repr(re.sub(r"\s+"," ",qtxt)[-220:]))
            bi+=1
        pos=s+5
