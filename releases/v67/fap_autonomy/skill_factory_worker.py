from __future__ import annotations
import hashlib,json,os,tempfile
from pathlib import Path
from typing import Any,Dict,List,Optional
class SkillFactoryHandoff:
    def __init__(self,inbox:str,outbox:str,processed:str):
        self.inbox=Path(inbox);self.outbox=Path(outbox);self.processed=Path(processed)
        for p in (self.inbox,self.outbox,self.processed):p.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def _load_request(path:Path)->Dict[str,Any]:
        obj=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj,dict):raise ValueError("Skill Factory request must be an object")
        if obj.get("metadata",{}).get("executable",True):raise ValueError("Skill Factory inbox may contain only non-executable specifications")
        if not str(obj.get("capability_id","")).strip():raise ValueError("capability_id missing")
        return obj
    def pending_requests(self)->List[Path]:return sorted(p for p in self.inbox.glob("*.json") if p.is_file())
    def claim_next(self)->Optional[Dict[str,Any]]:
        for path in self.pending_requests():
            obj=self._load_request(path);raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();claimed=self.processed/f"claimed__{digest[:16]}__{path.name}"
            try:os.replace(path,claimed)
            except FileNotFoundError:continue
            return {"request":obj,"request_sha256":digest,"claimed_path":str(claimed)}
        return None
    def publish_candidate_manifest(self,*,request_sha256:str,manifest:Dict[str,Any])->Dict[str,Any]:
        if not isinstance(manifest,dict):raise ValueError("candidate manifest must be an object")
        rec={"request_sha256":str(request_sha256),"manifest":manifest};canonical=json.dumps(rec,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8");digest=hashlib.sha256(canonical).hexdigest();final=self.outbox/f"candidate__{digest[:20]}.json"
        if final.exists():return {"written":False,"duplicate":True,"path":str(final),"sha256":digest}
        fd,tmp=tempfile.mkstemp(prefix=".tmp-v65-",suffix=".json",dir=str(self.outbox))
        try:
            with os.fdopen(fd,"wb") as f:f.write(canonical);f.flush();os.fsync(f.fileno())
            os.replace(tmp,final)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return {"written":True,"duplicate":False,"path":str(final),"sha256":digest}
    def collect_candidate(self,*,request_sha256:str)->Optional[Dict[str,Any]]:
        for path in sorted(self.outbox.glob("candidate__*.json")):
            obj=json.loads(path.read_text(encoding="utf-8"))
            if obj.get("request_sha256")==request_sha256:
                manifest=obj.get("manifest")
                if not isinstance(manifest,dict):raise ValueError("invalid candidate outbox record")
                return {"path":str(path),"manifest":manifest}
        return None
