from __future__ import annotations

from math import isfinite
from pathlib import Path
import json
import re
from typing import Any

from .engine import OPERATORS

_ALLOWED_STAGES = {"ephemeral", "shadow", "consolidated", "rejected"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_experience_payload(payload: Any) -> list[dict]:
    """Validate persisted V79 experience before it is trusted by a runtime.

    This is structural validation, not evidence authentication. It rejects
    malformed or internally contradictory records fail-closed so a damaged
    store cannot silently become an operator prior.
    """
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("invalid creativity experience payload")
    records = payload["records"]
    if not isinstance(records, list):
        raise ValueError("invalid creativity experience records")

    seen: set[str] = set()
    validated: list[dict] = []
    required = {
        "task_id", "task_text", "operator", "candidate_digest",
        "evidence_id", "reward", "verified", "stage",
    }
    for raw in records:
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("invalid creativity experience record schema")
        record = dict(raw)
        if not isinstance(record["task_id"], str) or not record["task_id"].strip():
            raise ValueError("invalid creativity task_id")
        if not isinstance(record["task_text"], str) or not record["task_text"].strip():
            raise ValueError("invalid creativity task_text")
        if record["operator"] not in OPERATORS:
            raise ValueError("unknown creativity operator")
        if not isinstance(record["candidate_digest"], str) or not _SHA256_RE.fullmatch(record["candidate_digest"]):
            raise ValueError("invalid creativity candidate digest")
        evidence_id = record["evidence_id"]
        if not isinstance(evidence_id, str) or not evidence_id.strip() or evidence_id in seen:
            raise ValueError("invalid or duplicate creativity evidence_id")
        seen.add(evidence_id)
        if type(record["reward"]) not in {int, float} or not isfinite(float(record["reward"])) or not 0.0 <= float(record["reward"]) <= 1.0:
            raise ValueError("invalid creativity reward")
        if type(record["verified"]) is not bool:
            raise ValueError("invalid creativity verified flag")
        if record["stage"] not in _ALLOWED_STAGES:
            raise ValueError("invalid creativity stage")
        successful = record["verified"] and float(record["reward"]) >= 0.70
        if (record["stage"] == "rejected") == successful:
            raise ValueError("contradictory creativity verification state")
        validated.append(record)
    return validated


def validate_experience_file(path: str | Path) -> list[dict]:
    """Read and validate one persisted creativity ledger."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_experience_payload(payload)
