from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable, Iterable

from fap_repository_executor import FileEdit
from fap_repository_verifier import CandidateAttempt


RepairProvider = Callable[
    [tuple[FileEdit, ...], CandidateAttempt],
    Iterable[FileEdit] | None,
]


@dataclass(frozen=True)
class RepairGuardDecision:
    allowed: bool
    reason: str
    candidate_fingerprint: str
    failure_fingerprint: str


class GuardedRepairProvider:
    """Stop bounded repair from cycling through repeated candidates/failures."""

    VERSION = "fap.repository.repair_guard.v1"

    def __init__(self, provider: RepairProvider, *, max_seen: int = 16) -> None:
        if not callable(provider):
            raise TypeError("provider must be callable")
        if not 1 <= int(max_seen) <= 128:
            raise ValueError("max_seen must be in [1, 128]")
        self.provider = provider
        self.max_seen = int(max_seen)
        self._seen_candidates: list[str] = []
        self._seen_pairs: list[tuple[str, str]] = []
        self.last_decision: RepairGuardDecision | None = None

    def __call__(
        self,
        current: tuple[FileEdit, ...],
        attempt: CandidateAttempt,
    ) -> tuple[FileEdit, ...] | None:
        current_fp = candidate_fingerprint(current)
        failure_fp = verification_failure_fingerprint(attempt)
        pair = (current_fp, failure_fp)

        if pair in self._seen_pairs:
            self.last_decision = RepairGuardDecision(
                allowed=False,
                reason="repeated_candidate_failure_pair",
                candidate_fingerprint=current_fp,
                failure_fingerprint=failure_fp,
            )
            return None
        self._remember_pair(pair)
        self._remember_candidate(current_fp)

        proposal = self.provider(current, attempt)
        if proposal is None:
            self.last_decision = RepairGuardDecision(
                allowed=False,
                reason="provider_stopped",
                candidate_fingerprint=current_fp,
                failure_fingerprint=failure_fp,
            )
            return None

        next_edits = tuple(proposal)
        if not next_edits:
            self.last_decision = RepairGuardDecision(
                allowed=False,
                reason="provider_returned_empty",
                candidate_fingerprint=current_fp,
                failure_fingerprint=failure_fp,
            )
            return ()

        next_fp = candidate_fingerprint(next_edits)
        if next_fp == current_fp:
            self.last_decision = RepairGuardDecision(
                allowed=False,
                reason="repair_candidate_unchanged",
                candidate_fingerprint=next_fp,
                failure_fingerprint=failure_fp,
            )
            return None
        if next_fp in self._seen_candidates:
            self.last_decision = RepairGuardDecision(
                allowed=False,
                reason="repair_candidate_cycle_detected",
                candidate_fingerprint=next_fp,
                failure_fingerprint=failure_fp,
            )
            return None

        self._remember_candidate(next_fp)
        self.last_decision = RepairGuardDecision(
            allowed=True,
            reason="new_candidate",
            candidate_fingerprint=next_fp,
            failure_fingerprint=failure_fp,
        )
        return next_edits

    def _remember_candidate(self, value: str) -> None:
        if value not in self._seen_candidates:
            self._seen_candidates.append(value)
            if len(self._seen_candidates) > self.max_seen:
                del self._seen_candidates[0]

    def _remember_pair(self, value: tuple[str, str]) -> None:
        if value not in self._seen_pairs:
            self._seen_pairs.append(value)
            if len(self._seen_pairs) > self.max_seen:
                del self._seen_pairs[0]


def candidate_fingerprint(edits: Iterable[FileEdit]) -> str:
    rows = []
    for edit in edits:
        rows.append(
            {
                "path": edit.path,
                "operation": edit.operation,
                "before_sha256": edit.before_sha256,
                "content_sha256": (
                    sha256((edit.content or "").encode("utf-8")).hexdigest()
                    if edit.content is not None
                    else None
                ),
            }
        )
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def verification_failure_fingerprint(attempt: CandidateAttempt) -> str:
    errors = tuple(str(x) for x in attempt.verification.errors)
    commands = tuple(
        (
            row.name,
            row.phase,
            row.returncode,
            row.timed_out,
            row.output_limited,
            row.error,
        )
        for row in attempt.verification.commands
        if not row.passed
    )
    raw = json.dumps(
        {"errors": errors, "commands": commands},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()
