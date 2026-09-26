from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


class AttestationError(ValueError):
    pass


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_tree(directory: str) -> str:
    """Stable SHA-256 for a candidate slot; rejects symlinks."""
    root = Path(directory)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise AttestationError("slot must be an absolute non-symlink directory")
    h = hashlib.sha256()
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if p.is_symlink():
            raise AttestationError("slot contains symlink")
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix().encode("utf-8")
        data = p.read_bytes()
        h.update(len(rel).to_bytes(8, "big")); h.update(rel)
        h.update(len(data).to_bytes(8, "big")); h.update(data)
    return h.hexdigest()


@dataclass(frozen=True)
class VerifiedAttestation:
    attestation_id: str
    wrapper_id: str
    nonce: str
    slot_digest: str
    result_sha256: str
    issued_at_ms: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "attestation_id": self.attestation_id,
            "wrapper_id": self.wrapper_id,
            "nonce": self.nonce,
            "slot_digest": self.slot_digest,
            "result_sha256": self.result_sha256,
            "issued_at_ms": self.issued_at_ms,
            "attestation_verified": True,
        }


class AttestationVerifier:
    """Verify host-wrapper HMAC attestations.

    This is symmetric MAC attestation, not hardware or remote attestation. The HMAC key
    must remain in the trusted wrapper/verifier boundary and must never be exposed to
    candidate code.
    """

    def __init__(self, secret: bytes, *, allowed_wrapper_ids: Optional[Iterable[str]] = None,
                 max_age_ms: int = 120_000, max_future_skew_ms: int = 10_000):
        if not isinstance(secret, (bytes, bytearray)) or len(secret) < 32:
            raise ValueError("attestation secret must be at least 32 bytes")
        if max_age_ms < 1 or max_future_skew_ms < 0:
            raise ValueError("invalid attestation time limits")
        self.secret = bytes(secret)
        self.allowed = None if allowed_wrapper_ids is None else {str(x) for x in allowed_wrapper_ids}
        self.max_age_ms = int(max_age_ms)
        self.max_future_skew_ms = int(max_future_skew_ms)

    @staticmethod
    def _payload(att: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "wrapper_id": str(att.get("wrapper_id", "")),
            "nonce": str(att.get("nonce", "")),
            "slot_digest": str(att.get("slot_digest", "")),
            "result_sha256": str(att.get("result_sha256", "")),
            "issued_at_ms": int(att.get("issued_at_ms", 0)),
        }

    def verify(self, *, attestation: Mapping[str, Any], expected_nonce: str,
               expected_slot_digest: str, result: Any, now_ms: Optional[int] = None) -> VerifiedAttestation:
        if not isinstance(attestation, Mapping):
            raise AttestationError("attestation must be an object")
        payload = self._payload(attestation)
        mac = str(attestation.get("mac", "")).lower()
        if len(mac) != 64 or any(c not in "0123456789abcdef" for c in mac):
            raise AttestationError("invalid attestation MAC")
        if not payload["wrapper_id"] or not payload["nonce"]:
            raise AttestationError("wrapper_id and nonce are required")
        for field in ("slot_digest", "result_sha256"):
            value = str(payload[field]).lower()
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise AttestationError(f"{field} must be SHA-256 hex")
        if self.allowed is not None and payload["wrapper_id"] not in self.allowed:
            raise AttestationError("wrapper_id is not trusted")
        if payload["nonce"] != str(expected_nonce):
            raise AttestationError("attestation nonce mismatch")
        if payload["slot_digest"] != str(expected_slot_digest):
            raise AttestationError("attestation slot digest mismatch")
        result_sha = _sha256_bytes(_canonical_json(result))
        if payload["result_sha256"] != result_sha:
            raise AttestationError("attestation result digest mismatch")
        now = int(time.time() * 1000) if now_ms is None else int(now_ms)
        age = now - int(payload["issued_at_ms"])
        if age > self.max_age_ms:
            raise AttestationError("attestation expired")
        if age < -self.max_future_skew_ms:
            raise AttestationError("attestation timestamp too far in future")
        expected_mac = hmac.new(self.secret, _canonical_json(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected_mac):
            raise AttestationError("attestation MAC verification failed")
        attestation_id = _sha256_bytes(_canonical_json({**payload, "mac": mac}))
        return VerifiedAttestation(attestation_id, payload["wrapper_id"], payload["nonce"],
                                   payload["slot_digest"], payload["result_sha256"], payload["issued_at_ms"])


class AttestedSandboxRunner:
    """Strict client for a fixed trusted sandbox wrapper with HMAC result attestation."""

    def __init__(self, argv: Sequence[str], verifier: AttestationVerifier, *, timeout_s: float = 10.0,
                 max_output_bytes: int = 1_000_000, env: Optional[Mapping[str, str]] = None):
        if not argv or any(not isinstance(x, str) or not x for x in argv):
            raise ValueError("runner argv must be a fixed non-empty string sequence")
        if "-c" in argv:
            raise ValueError("inline runner code is forbidden")
        exe = Path(argv[0])
        if not exe.is_absolute() or not exe.is_file():
            raise ValueError("runner executable must be an absolute existing file")
        if timeout_s <= 0 or max_output_bytes < 128:
            raise ValueError("invalid runner limits")
        self.argv = list(argv)
        self.verifier = verifier
        self.timeout_s = float(timeout_s)
        self.max_output_bytes = int(max_output_bytes)
        self.env = None if env is None else {str(k): str(v) for k, v in env.items()}

    def execute(self, *, slot: str, request: Dict[str, Any]) -> Dict[str, Any]:
        slot_path = Path(slot)
        if not slot_path.is_absolute():
            raise AttestationError("slot must be absolute")
        slot_digest = digest_tree(str(slot_path.resolve()))
        nonce = secrets.token_hex(24)
        envelope = {
            "slot": str(slot_path.resolve()),
            "slot_digest": slot_digest,
            "nonce": nonce,
            "request": dict(request),
        }
        allow = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME")
        proc_env = {k: os.environ[k] for k in allow if k in os.environ}
        if self.env is not None:
            proc_env.update(self.env)
        cp = subprocess.run(
            self.argv,
            input=_canonical_json(envelope),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout_s,
            check=False,
            shell=False,
            env=proc_env,
        )
        if cp.returncode != 0:
            err = cp.stderr[:4096].decode("utf-8", errors="replace")
            raise AttestationError(f"trusted wrapper failed: rc={cp.returncode}: {err}")
        if len(cp.stdout) > self.max_output_bytes:
            raise AttestationError("trusted wrapper output exceeded limit")
        try:
            obj = json.loads(cp.stdout.decode("utf-8"))
        except Exception as exc:
            raise AttestationError("trusted wrapper returned invalid JSON") from exc
        if not isinstance(obj, dict) or "result" not in obj or "attestation" not in obj:
            raise AttestationError("trusted wrapper response missing result/attestation")
        verified = self.verifier.verify(
            attestation=obj["attestation"], expected_nonce=nonce,
            expected_slot_digest=slot_digest, result=obj["result"],
        )
        return {
            "result": obj["result"],
            "verified_attestation": verified,
            **verified.as_dict(),
        }
