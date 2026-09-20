from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

_ALLOWED_STAGES = {"candidate", "testing", "shadow", "active", "rejected"}
_ALLOWED_TRANSITIONS = {
    "candidate": {"testing", "rejected"},
    "testing": {"shadow", "rejected"},
    # Re-running the supported promotion loop for a partially shadowed primitive
    # re-enters testing before returning to shadow.
    "shadow": {"testing", "active", "rejected"},
    "active": set(),
    "rejected": set(),
}
_KINDS = {"string", "number", "list"}
_OPS = {
    "string": {"strip", "lower", "upper", "prefix", "suffix", "replace"},
    "number": {"add", "sub", "mul", "div", "abs", "neg", "round", "clamp"},
    "list": {"unique", "sort", "reverse", "take", "drop", "append", "prepend"},
}
_BANNED = {
    "eval", "exec", "import", "open", "file", "shell", "subprocess", "system",
    "spawn", "network", "socket", "http", "read", "write", "delete", "random",
}
_CANDIDATE_KEYS = {
    "primitive_id", "name", "input_kind", "output_kind",
    "program", "tests", "description",
}


def _expected_primitive_id(candidate: dict) -> str:
    program = []
    for raw in candidate["program"]:
        if not isinstance(raw, dict) or set(raw) != {"op", "args"}:
            raise ValueError("invalid primitive instruction schema")
        op = raw["op"]
        args = raw["args"]
        if not isinstance(op, str) or not isinstance(args, list):
            raise ValueError("invalid primitive instruction")
        program.append((op, tuple(args)))
    payload = json.dumps(
        [
            candidate["name"],
            candidate["input_kind"],
            candidate["output_kind"],
            program,
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return "primitive:" + sha256(payload.encode()).hexdigest()[:16]


def _validate_candidate(candidate: Any, pid: str, name: str) -> None:
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_KEYS:
        raise ValueError("invalid primitive candidate schema")
    if candidate["primitive_id"] != pid or candidate["name"] != name:
        raise ValueError("primitive candidate identity mismatch")
    input_kind = candidate["input_kind"]
    output_kind = candidate["output_kind"]
    if input_kind not in _KINDS or output_kind not in _KINDS:
        raise ValueError("invalid primitive candidate kind")
    program = candidate["program"]
    if not isinstance(program, list) or not program:
        raise ValueError("invalid primitive candidate program")
    for raw in program:
        if not isinstance(raw, dict) or set(raw) != {"op", "args"}:
            raise ValueError("invalid primitive instruction schema")
        op = raw["op"]
        args = raw["args"]
        if not isinstance(op, str) or not isinstance(args, list):
            raise ValueError("invalid primitive instruction")
        normalized = op.lower().strip()
        if normalized in _BANNED or any(token in normalized for token in _BANNED):
            raise ValueError("banned primitive instruction")
        if normalized not in _OPS[input_kind]:
            raise ValueError("unsupported primitive instruction")
    tests = candidate["tests"]
    if not isinstance(tests, list):
        raise ValueError("invalid primitive candidate tests")
    if not isinstance(candidate["description"], str):
        raise ValueError("invalid primitive candidate description")
    if _expected_primitive_id(candidate) != pid:
        raise ValueError("primitive candidate digest mismatch")


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
        if (
            not isinstance(raw, dict)
            or set(raw) != {"primitive_id", "name", "stage", "candidate", "evidence"}
        ):
            raise ValueError("invalid primitive registry record schema")
        pid = raw["primitive_id"]
        if not isinstance(pid, str) or not pid.startswith("primitive:") or pid in seen:
            raise ValueError("invalid or duplicate primitive_id")
        seen.add(pid)
        name = raw["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("invalid primitive name")
        stage = raw["stage"]
        if stage not in _ALLOWED_STAGES:
            raise ValueError("invalid primitive stage")

        _validate_candidate(raw["candidate"], pid, name)

        evidence = raw["evidence"]
        if not isinstance(evidence, dict):
            raise ValueError("invalid primitive evidence")
        transitions = evidence.get("transitions")
        if (
            not isinstance(transitions, list)
            or not transitions
            or transitions[0] != "candidate"
            or transitions[-1] != stage
            or any(x not in _ALLOWED_STAGES for x in transitions)
        ):
            raise ValueError("invalid primitive transition history")
        previous = transitions[0]
        for current in transitions[1:]:
            if current not in _ALLOWED_TRANSITIONS.get(previous, set()):
                raise ValueError("illegal primitive stage transition")
            previous = current

        shadow = evidence.get("shadow_successes", 0)
        if type(shadow) is not int or shadow < 0:
            raise ValueError("invalid primitive shadow evidence")
        if stage == "active" and (
            shadow < 3 or evidence.get("promotion") != "passed"
        ):
            raise ValueError("active primitive lacks promotion evidence")
        validated.append(dict(raw))
    return validated
