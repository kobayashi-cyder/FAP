from __future__ import annotations
import hashlib,json,re
from dataclasses import dataclass
from typing import Any,Callable,Mapping,Sequence

HEX64=re.compile(r'^[0-9a-f]{64}$')
FORBIDDEN=('token','password','secret','audio','image','video','device_id','absolute_path','timestamp','wall_clock','random_value')

def _check(v:Any,path:str='root')->None:
    if isinstance(v,float): raise ValueError(f'floats forbidden: {path}')
    if isinstance(v,dict):
        for k,x in v.items():
            if not isinstance(k,str): raise ValueError('keys must be strings')
            lk=k.lower()
            if any(f in lk for f in FORBIDDEN): raise ValueError(f'nondeterministic/private field: {k}')
            _check(x,path+'.'+k)
    elif isinstance(v,(list,tuple)):
        for i,x in enumerate(v): _check(x,f'{path}[{i}]')
    elif v is not None and not isinstance(v,(str,int,bool)): raise ValueError(f'unsupported type: {path}')

def canonical(v:Any)->bytes:
    _check(v)
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()

@dataclass(frozen=True)
class ReplayEnvelope:
    schema:int; config:Mapping[str,Any]; events:tuple[Mapping[str,Any],...]; digest:str

@dataclass(frozen=True)
class ReplayVerification:
    ok:bool; reason:str

@dataclass(frozen=True)
class ReplayResult:
    ok:bool; result:Any=None; result_digest:str|None=None; reason:str=''

def canonicalize_replay(events:Sequence[Mapping[str,Any]],config:Mapping[str,Any],*,schema:int=1)->ReplayEnvelope:
    if schema!=1: raise ValueError('unsupported schema')
    if not config: raise ValueError('config required')
    ids=[]
    for i,e in enumerate(events):
        if e.get('id') is None: raise ValueError(f'event id required at {i}')
        ids.append(str(e['id']))
    if len(ids)!=len(set(ids)): raise ValueError('duplicate event id')
    body={'schema':schema,'config':dict(config),'events':[dict(e) for e in events]}
    return ReplayEnvelope(schema,dict(config),tuple(dict(e) for e in events),digest(body))

def verify_replay(envelope:ReplayEnvelope,events:Sequence[Mapping[str,Any]],config:Mapping[str,Any])->ReplayVerification:
    if envelope.schema!=1 or not HEX64.fullmatch(envelope.digest): return ReplayVerification(False,'malformed envelope')
    try: actual=canonicalize_replay(events,config,schema=envelope.schema)
    except (ValueError,TypeError) as e:return ReplayVerification(False,str(e))
    return ReplayVerification(actual.digest==envelope.digest,'match' if actual.digest==envelope.digest else 'digest mismatch')

def run_replay(events:Sequence[Mapping[str,Any]],reducer:Callable[[Any,Mapping[str,Any],Mapping[str,Any]],Any],config:Mapping[str,Any],*,initial:Any=None)->ReplayResult:
    try:
        canonicalize_replay(events,config)
        state=initial
        for event in events: state=reducer(state,dict(event),dict(config))
        return ReplayResult(True,state,digest({'result':state}))
    except Exception as e:
        return ReplayResult(False,reason=f'{type(e).__name__}: {e}')
