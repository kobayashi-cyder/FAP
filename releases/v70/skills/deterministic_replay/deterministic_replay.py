from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


def _canonical(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class ReplayStep:
    index: int
    observation: Mapping[str, Any]
    decision: Mapping[str, Any]
    action: Mapping[str, Any]
    random_seed: int

    def digest(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()


@dataclass(frozen=True)
class ReplayTrace:
    version: int
    steps: tuple[ReplayStep, ...]

    def digest(self) -> str:
        body = {"version": int(self.version), "step_digests": [step.digest() for step in self.steps]}
        return hashlib.sha256(_canonical(body)).hexdigest()


def build_trace(rows: Iterable[Mapping[str, Any]], *, version: int = 1) -> ReplayTrace:
    steps = []
    for i, row in enumerate(rows):
        steps.append(
            ReplayStep(
                index=i,
                observation=dict(row.get("observation") or {}),
                decision=dict(row.get("decision") or {}),
                action=dict(row.get("action") or {}),
                random_seed=int(row.get("random_seed", 0)),
            )
        )
    return ReplayTrace(version=int(version), steps=tuple(steps))


def verify_replay(expected_digest: str, rows: Iterable[Mapping[str, Any]], *, version: int = 1) -> bool:
    return build_trace(rows, version=version).digest() == str(expected_digest).lower()
