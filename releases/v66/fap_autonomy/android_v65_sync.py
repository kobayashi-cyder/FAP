from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from typing import Any,Dict
class AndroidV65StateSync:
    def __init__(self,out_path:str):self.out=Path(out_path);self.out.parent.mkdir(parents=True,exist_ok=True)
    def write(self,*,active_state:Dict[str,Any],canary:Dict[str,Dict[str,Any]],quarantine:Dict[str,Dict[str,Any]])->Dict[str,Any]:
        active={}
        for cap,e in sorted((active_state.get("active") or {}).items()):active[cap]={"candidate_digest":e.get("candidate_digest"),"activated_at":e.get("activated_at"),"source":e.get("source"),"baseline_quality":e.get("baseline_quality"),"baseline_latency_ms":e.get("baseline_latency_ms"),"canary":canary.get(cap,{}),"quarantine":quarantine.get(cap,{})}
        data={"schema":2,"active":active};fd,tmp=tempfile.mkstemp(prefix=self.out.name+".",dir=str(self.out.parent))
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2,sort_keys=True);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.out)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return data
