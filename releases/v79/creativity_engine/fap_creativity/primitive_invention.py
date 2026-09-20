from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json, math, time
from pathlib import Path
from typing import Any, Optional, Sequence

KINDS={"string","number","list"}
OPS={
 "string":{"strip","lower","upper","prefix","suffix","replace"},
 "number":{"add","sub","mul","div","abs","neg","round","clamp"},
 "list":{"unique","sort","reverse","take","drop","append","prepend"},
}
BANNED={"eval","exec","import","open","file","shell","subprocess","system","spawn","network","socket","http","read","write","delete","random"}

@dataclass(frozen=True)
class Instruction:
    op:str
    args:tuple[Any,...]=()

@dataclass(frozen=True)
class PrimitiveTestCase:
    value:Any
    expected:Any
    boundary:bool=False
    label:str=""

@dataclass(frozen=True)
class PrimitiveCandidate:
    primitive_id:str
    name:str
    input_kind:str
    output_kind:str
    program:tuple[Instruction,...]
    tests:tuple[PrimitiveTestCase,...]
    description:str=""

@dataclass(frozen=True)
class SandboxResult:
    ok:bool
    output:Any=None
    timed_out:bool=False
    elapsed_ms:float=0.0
    error:str=""

@dataclass(frozen=True)
class PromotionDecision:
    primitive_id:str
    stage:str
    promoted:bool
    reasons:tuple[str,...]=()
    unit_passed:int=0
    unit_total:int=0
    boundary_passed:bool=False
    deterministic:bool=False
    timeout_free:bool=False
    shadow_successes:int=0

class MiniIRSandbox:
    """Non-Turing-complete, allow-listed execution sandbox for invented primitives."""
    def __init__(self, timeout_ms:float=25.0, max_ops:int=32, max_items:int=2048):
        self.timeout_ms=max(1.0,float(timeout_ms)); self.max_ops=max(1,int(max_ops)); self.max_items=max(8,int(max_items))

    def validate(self,c:PrimitiveCandidate)->tuple[bool,tuple[str,...]]:
        e=[]
        if c.input_kind not in KINDS or c.output_kind not in KINDS: e.append("unsupported kind")
        if not c.name.strip(): e.append("name is required")
        if not c.program: e.append("program is empty")
        if len(c.program)>self.max_ops: e.append("program exceeds operation budget")
        allowed=OPS.get(c.input_kind,set())
        for i,ins in enumerate(c.program):
            op=ins.op.lower().strip()
            if op in BANNED or any(x in op for x in BANNED): e.append(f"instruction {i} is banned: {ins.op}")
            elif op not in allowed: e.append(f"instruction {i} is not allowed: {ins.op}")
            try: self._safe(list(ins.args))
            except Exception as ex: e.append(f"instruction {i} args invalid: {ex}")
        return not e,tuple(e)

    def execute(self,c:PrimitiveCandidate,value:Any)->SandboxResult:
        valid,errors=self.validate(c)
        if not valid: return SandboxResult(False,error="; ".join(errors))
        t=time.perf_counter()
        try:
            self._kind(c.input_kind,value); self._safe(value); x=value
            for ins in c.program:
                self._timeout(t); x=self._apply(c.input_kind,x,ins); self._safe(x)
            self._timeout(t); self._kind(c.output_kind,x)
            return SandboxResult(True,x,False,round((time.perf_counter()-t)*1000,4))
        except TimeoutError as ex:
            return SandboxResult(False,timed_out=True,elapsed_ms=round((time.perf_counter()-t)*1000,4),error=str(ex))
        except Exception as ex:
            return SandboxResult(False,elapsed_ms=round((time.perf_counter()-t)*1000,4),error=f"{type(ex).__name__}: {ex}")

    def _timeout(self,t):
        if (time.perf_counter()-t)*1000>self.timeout_ms: raise TimeoutError("sandbox execution exceeded timeout")
    def _kind(self,k,v):
        if k=="string" and not isinstance(v,str): raise TypeError("expected string")
        if k=="number" and (isinstance(v,bool) or not isinstance(v,(int,float))): raise TypeError("expected number")
        if k=="list" and not isinstance(v,list): raise TypeError("expected list")
    def _safe(self,v,depth=0):
        if depth>8: raise ValueError("nesting too deep")
        if v is None or isinstance(v,(str,bool,int)): return
        if isinstance(v,float):
            if not math.isfinite(v): raise ValueError("non-finite number")
            return
        if isinstance(v,list):
            if len(v)>self.max_items: raise ValueError("list too large")
            for x in v:self._safe(x,depth+1)
            return
        if isinstance(v,dict):
            if len(v)>128 or any(not isinstance(k,str) for k in v): raise ValueError("invalid mapping")
            for x in v.values():self._safe(x,depth+1)
            return
        raise TypeError("unsupported value")
    @staticmethod
    def _num(v):
        if isinstance(v,bool) or not isinstance(v,(int,float)) or (isinstance(v,float) and not math.isfinite(v)): raise TypeError("numeric argument required")
        return v
    @staticmethod
    def _key(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    def _apply(self,k,v,ins):
        op,a=ins.op.lower(),ins.args
        if k=="string":
            if op=="strip": return v.strip()
            if op=="lower": return v.lower()
            if op=="upper": return v.upper()
            if op=="prefix": return str(a[0])+v
            if op=="suffix": return v+str(a[0])
            if op=="replace": return v.replace(str(a[0]),str(a[1]))
        if k=="number":
            if op=="add": return v+self._num(a[0])
            if op=="sub": return v-self._num(a[0])
            if op=="mul": return v*self._num(a[0])
            if op=="div":
                d=self._num(a[0])
                if d==0: raise ZeroDivisionError
                return v/d
            if op=="abs": return abs(v)
            if op=="neg": return -v
            if op=="round": return round(v,int(a[0]) if a else 0)
            if op=="clamp":
                lo,hi=self._num(a[0]),self._num(a[1])
                if lo>hi: raise ValueError("invalid clamp")
                return min(hi,max(lo,v))
        if k=="list":
            if op=="unique":
                out=[]; seen=set()
                for x in v:
                    q=self._key(x)
                    if q not in seen: seen.add(q); out.append(x)
                return out
            if op=="sort": return sorted(v,key=self._key)
            if op=="reverse": return list(reversed(v))
            if op=="take": return v[:max(0,int(a[0]))]
            if op=="drop": return v[max(0,int(a[0])):]
            if op=="append": return v+[a[0]]
            if op=="prepend": return [a[0]]+v
        raise ValueError(f"unhandled instruction: {op}")

class PrimitiveInventor:
    """Searches bounded Mini-IR programs and invents one matching all demonstrations."""
    def __init__(self,sandbox:Optional[MiniIRSandbox]=None): self.sandbox=sandbox or MiniIRSandbox()
    def compose(self,*,name,input_kind,program,tests,description="",output_kind=None):
        p=tuple(x if isinstance(x,Instruction) else Instruction(str(x[0]),tuple(x[1:])) for x in program)
        out=output_kind or input_kind
        payload=json.dumps([name,input_kind,out,[(x.op,x.args) for x in p]],ensure_ascii=False,sort_keys=True)
        pid="primitive:"+sha256(payload.encode()).hexdigest()[:16]
        return PrimitiveCandidate(pid,str(name),str(input_kind),str(out),p,tuple(tests),str(description))
    def invent_from_examples(self,*,name,input_kind,examples,description="",max_depth=2):
        examples=tuple(examples)
        if input_kind not in KINDS or not examples: raise ValueError("invalid invention request")
        atoms=self._atoms(input_kind,examples)
        programs=[(x,) for x in atoms]
        if max_depth>=2: programs += [(a,b) for a in atoms for b in atoms]
        for p in programs:
            c=self.compose(name=name,input_kind=input_kind,program=p,tests=examples,description=description)
            if all((r:=self.sandbox.execute(c,t.value)).ok and r.output==t.expected for t in examples): return c
        raise ValueError("no safe Mini-IR primitive matched all demonstrations")
    def _atoms(self,k,e):
        a=[]
        if k=="string": a=[Instruction("strip"),Instruction("lower"),Instruction("upper")]
        elif k=="number":
            a=[Instruction("abs"),Instruction("neg"),Instruction("round",(0,))]
            x,y=e[0].value,e[0].expected
            if isinstance(x,(int,float)) and not isinstance(x,bool) and isinstance(y,(int,float)) and not isinstance(y,bool):
                a += [Instruction("add",(y-x,)),Instruction("sub",(x-y,))]
                if x!=0:a.append(Instruction("mul",(y/x,)))
                if y!=0:a.append(Instruction("div",(x/y,)))
        elif k=="list": a=[Instruction("unique"),Instruction("sort"),Instruction("reverse")]
        d={json.dumps([x.op,x.args],ensure_ascii=False,sort_keys=True):x for x in a}; return tuple(d.values())

class SkillRegistry:
    """candidate -> testing -> shadow -> active/rejected persistent registry."""
    def __init__(self,path:Optional[str|Path]=None):
        self.path=Path(path) if path else None; self.records={}
        if self.path and self.path.is_file():
            for r in json.loads(self.path.read_text(encoding="utf-8")).get("records",[]): self.records[r["primitive_id"]]=r
    def register(self,c):
        if c.primitive_id not in self.records:
            self.records[c.primitive_id]={"primitive_id":c.primitive_id,"name":c.name,"stage":"candidate","candidate":self._dump(c),"evidence":{"transitions":["candidate"],"shadow_successes":0}}; self._save()
        return self.records[c.primitive_id]
    def transition(self,pid,stage,**evidence):
        if stage not in {"candidate","testing","shadow","active","rejected"}: raise ValueError("invalid stage")
        r=self.records[pid]; r["stage"]=stage; r["evidence"].setdefault("transitions",[]).append(stage); r["evidence"].update(evidence); self._save(); return r
    def shadow_success(self,pid):
        r=self.records[pid]; n=int(r["evidence"].get("shadow_successes",0))+1; r["evidence"]["shadow_successes"]=n; self._save(); return n
    def get(self,pid): return self.records.get(pid)
    def active(self): return [r for r in self.records.values() if r["stage"]=="active"]
    def candidate(self,pid):
        q=self.records[pid]["candidate"]
        return PrimitiveCandidate(q["primitive_id"],q["name"],q["input_kind"],q["output_kind"],tuple(Instruction(x["op"],tuple(x["args"])) for x in q["program"]),tuple(PrimitiveTestCase(**x) for x in q["tests"]),q.get("description",""))
    def _save(self):
        if not self.path:return
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(self.path.suffix+".tmp")
        tmp.write_text(json.dumps({"schema":"fap.primitive-registry.v1","records":list(self.records.values())},ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(self.path)
    @staticmethod
    def _dump(c):
        return {"primitive_id":c.primitive_id,"name":c.name,"input_kind":c.input_kind,"output_kind":c.output_kind,"program":[{"op":x.op,"args":list(x.args)} for x in c.program],"tests":[asdict(x) for x in c.tests],"description":c.description}

class PrimitivePromotionLoop:
    """Primitive Inventor -> Sandbox -> Registry -> promotion decision closed loop."""
    def __init__(self,*,sandbox=None,registry=None,min_unit_tests=5,min_shadow_successes=3,determinism_repeats=3):
        self.sandbox=sandbox or MiniIRSandbox(); self.registry=registry or SkillRegistry(); self.min_unit_tests=max(5,int(min_unit_tests)); self.min_shadow=max(3,int(min_shadow_successes)); self.repeats=max(2,int(determinism_repeats))
    def evaluate(self,c:PrimitiveCandidate,*,shadow_cases:Sequence[PrimitiveTestCase]=()):
        self.registry.register(c); ok,errors=self.sandbox.validate(c)
        if not ok:self.registry.transition(c.primitive_id,"rejected",reasons=list(errors)); return PromotionDecision(c.primitive_id,"rejected",False,errors,unit_total=len(c.tests))
        self.registry.transition(c.primitive_id,"testing"); reasons=[]; passed=0; timeout_free=True
        if len(c.tests)<self.min_unit_tests:reasons.append(f"requires at least {self.min_unit_tests} automatic tests")
        for i,t in enumerate(c.tests):
            r=self.sandbox.execute(c,t.value); timeout_free &= not r.timed_out
            if r.ok and r.output==t.expected: passed+=1
            else: reasons.append(f"unit test failed: {t.label or i+1}")
        boundaries=[t for t in c.tests if t.boundary]
        boundary=bool(boundaries) and all((r:=self.sandbox.execute(c,t.value)).ok and r.output==t.expected for t in boundaries)
        if not boundaries:reasons.append("at least one boundary test is required")
        elif not boundary:reasons.append("boundary test failed")
        deterministic=self._deterministic(c)
        if not deterministic:reasons.append("determinism check failed")
        if not timeout_free:reasons.append("sandbox timeout occurred")
        if passed!=len(c.tests):reasons.append("not all automatic tests passed")
        if reasons:
            reasons=tuple(dict.fromkeys(reasons)); self.registry.transition(c.primitive_id,"rejected",reasons=list(reasons),unit_passed=passed,unit_total=len(c.tests),boundary_passed=boundary,deterministic=deterministic,timeout_free=timeout_free)
            return PromotionDecision(c.primitive_id,"rejected",False,reasons,passed,len(c.tests),boundary,deterministic,timeout_free,0)
        self.registry.transition(c.primitive_id,"shadow",unit_passed=passed,unit_total=len(c.tests),boundary_passed=True,deterministic=True,timeout_free=True)
        shadow=int(self.registry.get(c.primitive_id)["evidence"].get("shadow_successes",0))
        for i,t in enumerate(shadow_cases):
            r=self.sandbox.execute(c,t.value)
            if not (r.ok and not r.timed_out and r.output==t.expected):
                reason=f"shadow task failed: {t.label or i+1}"; self.registry.transition(c.primitive_id,"rejected",reasons=[reason])
                return PromotionDecision(c.primitive_id,"rejected",False,(reason,),passed,len(c.tests),True,True,True,shadow)
            shadow=self.registry.shadow_success(c.primitive_id)
            if shadow>=self.min_shadow:break
        if shadow>=self.min_shadow:
            self.registry.transition(c.primitive_id,"active",promotion="passed")
            return PromotionDecision(c.primitive_id,"active",True,(),passed,len(c.tests),True,True,True,shadow)
        return PromotionDecision(c.primitive_id,"shadow",False,(f"needs {self.min_shadow-shadow} more successful shadow task(s)",),passed,len(c.tests),True,True,True,shadow)
    def execute_active(self,pid,value):
        r=self.registry.get(pid)
        if not r or r["stage"]!="active":return SandboxResult(False,error="primitive is not active")
        return self.sandbox.execute(self.registry.candidate(pid),value)
    def _deterministic(self,c):
        for t in c.tests[:3]:
            out=[]
            for _ in range(self.repeats):
                r=self.sandbox.execute(c,t.value)
                if not r.ok or r.timed_out:return False
                out.append(json.dumps(r.output,ensure_ascii=False,sort_keys=True))
            if len(set(out))!=1:return False
        return True
