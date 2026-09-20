from __future__ import annotations

from typing import Any

_ALLOWED_STAGES = {"candidate", "testing", "shadow", "active", "rejected"}
_ALLOWED_TRANSITIONS = {
    "candidate": {"testing", "rejected"},
    "testing": {"shadow", "rejected"},
    "shadow": {"active", "rejected"},
    "active": set(),
    "rejected": set(),
}


def validate_primitive_registry_payload(payload: Any) -> list[dict]:
    """Validate persisted V80 primitive-registry state before it is trusted."""
    if not isinstance(payload, dict) or set(payload) != {"schema", "records"}:
        raise ValueError("invalid primitive registry payload")
    if payload["schema"] != "fap.primitive-registry.v1":
        raise ValueError("unsupported primitive registry schema")
    records = payload["records"]
    if not isinstance(records, list):
        raise ValueError("invalid primitive registry records")

    seen: set[str] = set()
    validated: list[dict] = []
    for raw in records:
        if not isinstance(raw, dict) or set(raw) != {"primitive_id", "name", "stage", "candidate", "evidence"}:
            raise ValueError("invalid primitive registry record schema")
        pid = raw["primitive_id"]
        if not isinstance(pid, str) or not pid.startswith("primitive:") or pid in seen:
            raise ValueError("invalid or duplicate primitive_id")
        seen.add(pid)
        if not isinstance(raw["name"], str) or not raw["name"].strip():
            raise ValueError("invalid primitive name")
        stage = raw["stage"]
        if stage not in _ALLOWED_STAGES:
            raise ValueError("invalid primitive stage")
        candidate = raw["candidate"]
        if not isinstance(candidate, dict) or candidate.get("primitive_id") != pid or candidate.get("name") != raw["name"]:
            raise ValueError("primitive candidate identity mismatch")
        evidence = raw["evidence"]
        if not isinstance(evidence, dict):
            raise ValueError("invalid primitive evidence")
        transitions = evidence.get("transitions")
        if not isinstance(transitions, list) or not transitions or transitions[0] != "candidate" or transitions[-1] != stage:
            raise ValueError("invalid primitive transition history")
        previous = transitions[0]
        for current in transitions[1:]:
            if current not in _ALLOWED_TRANSITIONS.get(previous, set()):
                raise ValueError("illegal primitive stage transition")
            previous = current
        shadow = evidence.get("shadow_successes", 0)
        if type(shadow) is not int or shadow < 0:
            raise ValueError("invalid primitive shadow evidence")
        if stage == "active" and (shadow < 3 or evidence.get("promotion") != "passed"):
            raise ValueError("active primitive lacks promotion evidence")
        validated.append(dict(raw))
    return validated
