from __future__ import annotations
import sqlite3,time
from contextlib import closing
from pathlib import Path
class QuarantineLedger:
    def __init__(self,path:str,*,candidate_threshold:int=3,family_threshold:int=5):
        if candidate_threshold<1 or family_threshold<1:raise ValueError("quarantine thresholds must be positive")
        self.path=str(path);self.candidate_threshold=int(candidate_threshold);self.family_threshold=int(family_threshold);Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con:con.execute("CREATE TABLE IF NOT EXISTS failures(event_id TEXT PRIMARY KEY,capability_id TEXT NOT NULL,candidate_digest TEXT NOT NULL,family TEXT NOT NULL,reason TEXT NOT NULL,created_at REAL NOT NULL)")
    def record_failure(self,*,event_id,capability_id,candidate_digest,reason,family=""):
        inserted=True
        try:
            with closing(sqlite3.connect(self.path)) as con:con.execute("INSERT INTO failures VALUES(?,?,?,?,?,?)",(str(event_id),str(capability_id),str(candidate_digest),str(family or ""),str(reason),time.time()));con.commit()
        except sqlite3.IntegrityError:inserted=False
        s=self.status(capability_id=capability_id,candidate_digest=candidate_digest,family=family);s["inserted"]=inserted;return s
    def status(self,*,capability_id,candidate_digest,family=""):
        with closing(sqlite3.connect(self.path)) as con:
            cc=con.execute("SELECT COUNT(*) FROM failures WHERE capability_id=? AND candidate_digest=?",(capability_id,candidate_digest)).fetchone()[0];fc=con.execute("SELECT COUNT(*) FROM failures WHERE capability_id=? AND family=?",(capability_id,family)).fetchone()[0] if family else 0
        q=cc>=self.candidate_threshold or (bool(family) and fc>=self.family_threshold);return {"quarantined":bool(q),"candidate_failures":int(cc),"family_failures":int(fc),"candidate_threshold":self.candidate_threshold,"family_threshold":self.family_threshold}
    def is_quarantined(self,*,capability_id,candidate_digest,family=""):return bool(self.status(capability_id=capability_id,candidate_digest=candidate_digest,family=family)["quarantined"])
