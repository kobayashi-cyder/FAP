from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from .attestation import VerifiedAttestation
from .telemetry import normalize_runtime_telemetry

_HEX = set("0123456789abcdef")


def _canonical(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class AttestedRuntimeTelemetry:
    event_id: str
    request_id: str
    capability_id: str
    candidate_digest: str
    arm: str
    verified: bool
    success: bool
    quality: float
    latency_ms: float
    family: str
    attestation_verified: bool
    attestation_id: str
    wrapper_id: str
    stage_ratio: float
    production: bool
    emitted_at_ms: int

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_attested_telemetry(obj: Mapping[str, Any]) -> AttestedRuntimeTelemetry:
    base = normalize_runtime_telemetry(dict(obj))
    if obj.get("attestation_verified") is not True:
        raise ValueError("attestation_verified must be true")
    att_id = str(obj.get("attestation_id", "")).lower()
    if len(att_id) != 64 or any(c not in _HEX for c in att_id):
        raise ValueError("attestation_id must be a SHA-256 hex digest")
    wrapper_id = str(obj.get("wrapper_id", "")).strip()
    if not wrapper_id:
        raise ValueError("wrapper_id is required")
    ratio = float(obj.get("stage_ratio"))
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("stage_ratio must be in 0..1")
    if obj.get("production") is not True:
        raise ValueError("only production telemetry is accepted")
    emitted = int(obj.get("emitted_at_ms", 0))
    if emitted <= 0:
        raise ValueError("emitted_at_ms is required")
    return AttestedRuntimeTelemetry(
        event_id=base.event_id, request_id=base.request_id, capability_id=base.capability_id,
        candidate_digest=base.candidate_digest, arm=base.arm, verified=True,
        success=base.success, quality=base.quality, latency_ms=base.latency_ms,
        family=base.family, attestation_verified=True, attestation_id=att_id,
        wrapper_id=wrapper_id, stage_ratio=ratio, production=True, emitted_at_ms=emitted,
    )


class TelemetryVerifier:
    """Authenticate telemetry rows emitted by the trusted FAP runtime boundary."""

    def __init__(self, secret: bytes):
        if not isinstance(secret, (bytes, bytearray)) or len(secret) < 32:
            raise ValueError("telemetry secret must be at least 32 bytes")
        self.secret = bytes(secret)

    def verify(self, obj: Mapping[str, Any]) -> AttestedRuntimeTelemetry:
        raw = dict(obj)
        mac = str(raw.pop("telemetry_mac", "")).lower()
        if len(mac) != 64 or any(c not in _HEX for c in mac):
            raise ValueError("telemetry_mac is required")
        expected = hmac.new(self.secret, _canonical(raw), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError("telemetry MAC verification failed")
        return normalize_attested_telemetry(raw)


class FAPTelemetryEmitter:
    """Emit append-only production telemetry from a VerifiedAttestation object."""

    def __init__(self, path: str, secret: bytes):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(secret, (bytes, bytearray)) or len(secret) < 32:
            raise ValueError("telemetry secret must be at least 32 bytes")
        self.secret = bytes(secret)

    def emit(self, *, request_id: str, capability_id: str, candidate_digest: str, arm: str,
             success: bool, quality: float, latency_ms: float, family: str = "",
             stage_ratio: float, attestation: VerifiedAttestation) -> Dict[str, Any]:
        if not isinstance(attestation, VerifiedAttestation):
            raise ValueError("VerifiedAttestation from the trusted wrapper verifier is required")
        now = int(time.time() * 1000)
        seed = {
            "request_id": str(request_id), "capability_id": str(capability_id),
            "candidate_digest": str(candidate_digest), "arm": str(arm),
            "attestation_id": attestation.attestation_id,
            "nonce": uuid.uuid4().hex, "emitted_at_ms": now,
        }
        event_id = hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        raw = {
            "event_id": event_id, "request_id": str(request_id), "capability_id": str(capability_id),
            "candidate_digest": str(candidate_digest), "arm": str(arm), "verified": True,
            "success": bool(success), "quality": float(quality), "latency_ms": float(latency_ms),
            "family": str(family or ""), "attestation_verified": True,
            "attestation_id": attestation.attestation_id,
            "wrapper_id": attestation.wrapper_id, "stage_ratio": float(stage_ratio),
            "production": True, "emitted_at_ms": now,
        }
        normalized = normalize_attested_telemetry(raw)
        body = normalized.as_dict()
        body["telemetry_mac"] = hmac.new(self.secret, _canonical(body), hashlib.sha256).hexdigest()
        line = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line); f.flush(); os.fsync(f.fileno())
        return body
