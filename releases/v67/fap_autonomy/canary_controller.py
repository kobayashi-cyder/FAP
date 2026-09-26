from __future__ import annotations

import math, sqlite3, time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple
from .telemetry import RuntimeTelemetry

def _p95(values: Iterable[float]) -> float:
    xs=sorted(float(v) for v in values)
    return 0.0 if not xs else xs[max(0, math.ceil(0.95*len(xs))-1)]

@dataclass(frozen=True)
class CanaryDecision:
    status:str; ratio:float; stage_index:int; baseline_n:int; active_n:int; baseline_success:float; active_success:float; success_delta:float; baseline_quality:float; active_quality:float; quality_delta:float; latency_ratio:float; next_ratio:float|None=None
    def as_dict(self)->Dict[str,object]: return asdict(self)

class StagedCanaryController:
    def __init__(self,path:str,*,stages:Tuple[float,...]=(0.05,0.20,0.50,1.0),min_per_arm:int=8,max_success_drop:float=.08,max_quality_drop:float=.08,max_latency_ratio:float=1.5):
        if not stages or any(not 0.0<float(x)<=1.0 for x in stages): raise ValueError("stages must be ratios in (0,1]")
        if tuple(sorted(float(x) for x in stages))!=tuple(float(x) for x in stages): raise ValueError("stages must be increasing")
        if float(stages[-1])!=1.0: raise ValueError("final canary stage must be 1.0")
        if min_per_arm<1: raise ValueError("min_per_arm must be >= 1")
        self.path=str(path); self.stages=tuple(float(x) for x in stages); self.min_per_arm=int(min_per_arm); self.max_success_drop=float(max_success_drop); self.max_quality_drop=float(max_quality_drop); self.max_latency_ratio=float(max_latency_ratio)
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con:
            con.executescript("""CREATE TABLE IF NOT EXISTS canary_state(capability_id TEXT NOT NULL,candidate_digest TEXT NOT NULL,stage_index INTEGER NOT NULL,status TEXT NOT NULL,updated_at REAL NOT NULL,PRIMARY KEY(capability_id,candidate_digest));CREATE TABLE IF NOT EXISTS canary_obs(event_id TEXT PRIMARY KEY,capability_id TEXT NOT NULL,candidate_digest TEXT NOT NULL,stage_index INTEGER NOT NULL,arm TEXT NOT NULL,success INTEGER NOT NULL,quality REAL NOT NULL,latency REAL NOT NULL,created_at REAL NOT NULL);""")
    def start(self,capability_id,candidate_digest):
        capability_id=str(capability_id);candidate_digest=str(candidate_digest)
        with closing(sqlite3.connect(self.path)) as con:
            row=con.execute("SELECT stage_index,status FROM canary_state WHERE capability_id=? AND candidate_digest=?",(capability_id,candidate_digest)).fetchone()
            if not row: con.execute("INSERT INTO canary_state VALUES(?,?,?,?,?)",(capability_id,candidate_digest,0,"running",time.time()));con.commit()
        return self.state(capability_id,candidate_digest)
    def state(self,capability_id,candidate_digest):
        with closing(sqlite3.connect(self.path)) as con: row=con.execute("SELECT stage_index,status,updated_at FROM canary_state WHERE capability_id=? AND candidate_digest=?",(capability_id,candidate_digest)).fetchone()
        if not row:return {"exists":False,"status":"not_started","ratio":0.0,"stage_index":-1}
        idx=int(row[0]);return {"exists":True,"status":str(row[1]),"stage_index":idx,"ratio":self.stages[min(idx,len(self.stages)-1)],"updated_at":float(row[2])}
    def ratio(self,capability_id,candidate_digest):
        st=self.state(capability_id,candidate_digest);return float(st["ratio"]) if st["status"] in {"running","complete"} else 0.0
    def ingest(self,t:RuntimeTelemetry):
        st=self.state(t.capability_id,t.candidate_digest)
        if not st["exists"] or st["status"]!="running":return False
        try:
            with closing(sqlite3.connect(self.path)) as con: con.execute("INSERT INTO canary_obs VALUES(?,?,?,?,?,?,?,?,?)",(t.event_id,t.capability_id,t.candidate_digest,int(st["stage_index"]),t.arm,int(t.success),t.quality,t.latency_ms,time.time()));con.commit()
            return True
        except sqlite3.IntegrityError:return False
    def evaluate(self,capability_id,candidate_digest):
        st=self.state(capability_id,candidate_digest)
        if not st["exists"]:raise ValueError("canary not started")
        idx=int(st["stage_index"]);ratio=float(st["ratio"])
        if st["status"] in {"rolled_back","quarantined","complete"}:return CanaryDecision(st["status"],ratio,idx,0,0,0,0,0,0,0,0,1.0)
        with closing(sqlite3.connect(self.path)) as con: rows=con.execute("SELECT arm,success,quality,latency FROM canary_obs WHERE capability_id=? AND candidate_digest=? AND stage_index=?",(capability_id,candidate_digest,idx)).fetchall()
        by={arm:[r for r in rows if r[0]==arm] for arm in ("baseline","active")}
        def stat(rs):
            n=len(rs);return n,(sum(int(r[1]) for r in rs)/n if n else 0.0),(sum(float(r[2]) for r in rs)/n if n else 0.0),_p95(float(r[3]) for r in rs)
        bn,bs,bq,bl=stat(by["baseline"]);an,acs,aq,al=stat(by["active"]);sd=acs-bs;qd=aq-bq;lr=(al/bl) if bl>0 else (1.0 if al==0 else float("inf"));enough=bn>=self.min_per_arm and an>=self.min_per_arm
        if enough and (sd < -self.max_success_drop or qd < -self.max_quality_drop or lr > self.max_latency_ratio): status="rollback_required";next_ratio=None
        elif not enough: status="monitoring";next_ratio=ratio
        elif idx==len(self.stages)-1: status="complete";next_ratio=1.0;self._set_state(capability_id,candidate_digest,idx,"complete")
        else:
            ni=idx+1;next_ratio=self.stages[ni]
            if next_ratio>=1.0: status="complete";self._set_state(capability_id,candidate_digest,ni,"complete")
            else: status="advance";self._set_state(capability_id,candidate_digest,ni,"running")
        return CanaryDecision(status,ratio,idx,bn,an,bs,acs,sd,bq,aq,qd,lr,next_ratio)
    def mark_rolled_back(self,capability_id,candidate_digest,*,quarantined=False):
        st=self.state(capability_id,candidate_digest)
        if st["exists"]:self._set_state(capability_id,candidate_digest,int(st["stage_index"]),"quarantined" if quarantined else "rolled_back")
    def _set_state(self,capability_id,candidate_digest,stage_index,status):
        with closing(sqlite3.connect(self.path)) as con: con.execute("UPDATE canary_state SET stage_index=?,status=?,updated_at=? WHERE capability_id=? AND candidate_digest=?",(int(stage_index),str(status),time.time(),capability_id,candidate_digest));con.commit()
