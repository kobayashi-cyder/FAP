from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

@dataclass(frozen=True)
class RuntimeTelemetry:
    event_id: str
    request_id: str
    capability_id: str
    candidate_digest: str
    arm: str
    verified: bool
    success: bool
    quality: float
    latency_ms: float
    family: str = ""
    def as_dict(self) -> Dict[str, Any]: return asdict(self)

def normalize_runtime_telemetry(obj: Dict[str, Any]) -> RuntimeTelemetry:
    if not isinstance(obj, dict): raise ValueError("telemetry must be an object")
    event_id=str(obj.get("event_id","")).strip(); request_id=str(obj.get("request_id","")).strip(); capability_id=str(obj.get("capability_id","")).strip()
    digest=str(obj.get("candidate_digest","")).strip().lower(); arm=str(obj.get("arm","")).strip().lower()
    if not event_id or not request_id or not capability_id: raise ValueError("event_id, request_id and capability_id are required")
    if not _HEX64.fullmatch(digest): raise ValueError("candidate_digest must be a lowercase SHA-256 hex digest")
    if arm not in {"baseline","active"}: raise ValueError("arm must be baseline or active")
    if obj.get("verified") is not True: raise ValueError("only verified telemetry is accepted")
    quality=float(obj.get("quality")); latency=float(obj.get("latency_ms"))
    if not 0.0 <= quality <= 1.0: raise ValueError("quality must be in 0..1")
    if latency < 0.0: raise ValueError("latency_ms must be non-negative")
    return RuntimeTelemetry(event_id,request_id,capability_id,digest,arm,True,bool(obj.get("success")),quality,latency,str(obj.get("family","") or "").strip())

def parse_runtime_telemetry_json(line: str) -> RuntimeTelemetry:
    return normalize_runtime_telemetry(json.loads(line))
