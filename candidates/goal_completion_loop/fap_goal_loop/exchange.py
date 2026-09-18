from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


SCHEMA = "fca-fap.exchange.v1"


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class ExchangeCapsule:
    source_project: str
    source_commit: str
    capability: str
    mechanism: dict[str, Any]
    evidence: dict[str, Any]
    constraints: tuple[str, ...]
    digest: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ExchangeCapsule":
        if raw.get("schema") != SCHEMA:
            raise ValueError("unsupported exchange schema")
        project = str(raw.get("source_project", "")).strip()
        commit = str(raw.get("source_commit", "")).strip().lower()
        capability = str(raw.get("capability", "")).strip()
        mechanism = raw.get("mechanism")
        evidence = raw.get("evidence")
        constraints = raw.get("constraints", [])
        if project not in {"FAP", "FCA"}:
            raise ValueError("source_project must be FAP or FCA")
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            raise ValueError("source_commit must be a 40-char git sha")
        if not capability or not isinstance(mechanism, dict) or not isinstance(evidence, dict):
            raise ValueError("invalid capsule body")
        if not isinstance(constraints, list) or not all(isinstance(x, str) for x in constraints):
            raise ValueError("constraints must be strings")
        body = dict(raw)
        supplied = str(body.pop("digest", "")).strip().lower()
        digest = sha256(_canonical(body)).hexdigest()
        if supplied and supplied != digest:
            raise ValueError("exchange capsule digest mismatch")
        return cls(project, commit, capability, dict(mechanism), dict(evidence), tuple(constraints), digest)

    @classmethod
    def from_json(cls, text: str) -> "ExchangeCapsule":
        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise ValueError("capsule must be an object")
        return cls.from_dict(raw)
