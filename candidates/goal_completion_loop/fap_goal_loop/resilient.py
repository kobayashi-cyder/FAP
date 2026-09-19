from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable

from .goal_loop import ExecutionResult, GoalState


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry policy for transient capability failures."""

    max_attempts: int = 2
    retry_statuses: tuple[str, ...] = ("failed",)

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")
        allowed = {"failed", "blocked"}
        if not set(self.retry_statuses).issubset(allowed):
            raise ValueError("retry_statuses may contain only failed/blocked")


class ResilientCapabilityHandler:
    """Adds deterministic bounded retries around one capability handler.

    Retries are opt-in and never retry approval requests. Exceptions are converted
    to failed results so the goal loop can replan instead of crashing.
    """

    def __init__(self, handler: Callable[[str, Dict[str, Any], GoalState], Any], *, policy: RetryPolicy | None = None, retryable_errors: Iterable[str] = ("timeout", "temporarily_unavailable")) -> None:
        self.handler = handler
        self.policy = policy or RetryPolicy()
        self.retryable_errors = tuple(str(x).lower() for x in retryable_errors)

    def _normalize(self, raw: Any) -> ExecutionResult:
        if isinstance(raw, ExecutionResult):
            return raw
        if isinstance(raw, dict) and "status" in raw:
            return ExecutionResult(status=str(raw.get("status", "failed")), output=raw.get("output"), error=str(raw.get("error", "")), metadata=dict(raw.get("metadata") or {}))
        return ExecutionResult("ok", output=raw)

    def _may_retry(self, result: ExecutionResult) -> bool:
        if result.status not in self.policy.retry_statuses:
            return False
        error = result.error.lower()
        return any(token in error for token in self.retryable_errors)

    def __call__(self, instruction: str, metadata: Dict[str, Any], state: GoalState) -> ExecutionResult:
        attempts = 0
        last = ExecutionResult("failed", error="not_attempted")
        while attempts < self.policy.max_attempts:
            attempts += 1
            try:
                last = self._normalize(self.handler(instruction, metadata, state))
            except Exception as exc:
                last = ExecutionResult("failed", error=f"{type(exc).__name__}: {exc}")
            if last.status in {"ok", "needs_approval"} or not self._may_retry(last):
                break
        merged = dict(last.metadata)
        merged["attempts"] = attempts
        merged["retry_exhausted"] = attempts >= self.policy.max_attempts and self._may_retry(last)
        return ExecutionResult(last.status, output=last.output, error=last.error, metadata=merged)
