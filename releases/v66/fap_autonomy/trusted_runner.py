from __future__ import annotations
import json,os,subprocess
from pathlib import Path
from typing import Any,Dict,Iterable
class TrustedSandboxRunner:
    """Client for a preconfigured trusted OS/container sandbox wrapper."""
    def __init__(self,runner_argv:Iterable[str],*,timeout_s:float=10.0,max_output_bytes:int=1_000_000):
        argv=tuple(str(x) for x in runner_argv)
        if not argv:raise ValueError("runner_argv is required")
        if any(x in {"-c","/c"} for x in argv[1:]):raise ValueError("inline shell/code execution is not allowed in runner_argv")
        if timeout_s<=0 or max_output_bytes<1:raise ValueError("invalid runner limits")
        self.argv=argv;self.timeout_s=float(timeout_s);self.max_output_bytes=int(max_output_bytes)
    def execute(self,*,slot:str,request:Dict[str,Any])->Dict[str,Any]:
        p=Path(str(slot))
        if not p.is_absolute() or not p.is_dir() or p.is_symlink():raise ValueError("runner received invalid slot")
        payload=json.dumps({"slot":str(p.resolve()),"request":dict(request)},ensure_ascii=False,sort_keys=True).encode("utf-8");env={"PATH":os.environ.get("PATH",""),"PYTHONIOENCODING":"utf-8"}
        try:proc=subprocess.run(list(self.argv),input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,timeout=self.timeout_s,env=env,check=False)
        except subprocess.TimeoutExpired as exc:raise RuntimeError("trusted sandbox runner timed out") from exc
        if len(proc.stdout)>self.max_output_bytes or len(proc.stderr)>self.max_output_bytes:raise RuntimeError("trusted sandbox runner output exceeded limit")
        if proc.returncode!=0:raise RuntimeError(f"trusted sandbox runner failed: rc={proc.returncode}: {proc.stderr.decode('utf-8','replace')[-2000:]}")
        try:out=json.loads(proc.stdout.decode("utf-8"))
        except Exception as exc:raise RuntimeError("trusted sandbox runner returned invalid JSON") from exc
        if not isinstance(out,dict):raise RuntimeError("trusted sandbox runner result must be an object")
        return out
