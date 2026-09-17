from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from deterministic_replay import ReplayStep, ReplayTrace

Executor = Callable[[Mapping[str, Any], int, int], tuple[Mapping[str, Any], Mapping[str, Any]]]


def _canonical(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class ReplayRunResult:
    matched: bool
    expected_trace_digest: str
    actual_trace_digest: str
    divergence_index: int | None
    expected_step_digest: str | None
    actual_step_digest: str | None
    executed_steps: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_replay(trace: ReplayTrace, executor: Executor) -> ReplayRunResult:
    actual_steps: list[ReplayStep] = []
    divergence_index: int | None = None
    expected_step_digest: str | None = None
    actual_step_digest: str | None = None

    for expected in trace.steps:
        decision, action = executor(dict(expected.observation), int(expected.random_seed), int(expected.index))
        actual = ReplayStep(
            index=int(expected.index),
            observation=dict(expected.observation),
            decision=dict(decision),
            action=dict(action),
            random_seed=int(expected.random_seed),
        )
        actual_steps.append(actual)
        if divergence_index is None and actual.digest() != expected.digest():
            divergence_index = int(expected.index)
            expected_step_digest = expected.digest()
            actual_step_digest = actual.digest()

    actual_trace = ReplayTrace(version=int(trace.version), steps=tuple(actual_steps))
    expected_digest = trace.digest()
    actual_digest = actual_trace.digest()
    return ReplayRunResult(
        matched=divergence_index is None and expected_digest == actual_digest,
        expected_trace_digest=expected_digest,
        actual_trace_digest=actual_digest,
        divergence_index=divergence_index,
        expected_step_digest=expected_step_digest,
        actual_step_digest=actual_step_digest,
        executed_steps=len(actual_steps),
    )


def trace_chain_digest(trace: ReplayTrace) -> str:
    """Hash-chain steps so insertion/reordering changes all following chain state."""
    state = hashlib.sha256(f"fap-replay-v{trace.version}".encode("ascii")).digest()
    for step in trace.steps:
        state = hashlib.sha256(state + bytes.fromhex(step.digest())).digest()
    return state.hex()
