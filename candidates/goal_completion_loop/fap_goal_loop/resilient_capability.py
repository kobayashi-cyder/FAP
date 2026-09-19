from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping

from .goal_loop import ExecutionResult, GoalState, PlannedAction


@dataclass(frozen=True)
class CapabilityRetryPolicy:
    """Fail-closed retry contract for a capability handler.

    Retries are allowed only when the capability is explicitly declared
    idempotent and a non-empty justification is recorded. This prevents
    accidental replay of irreversible/external side effects.
    """

    max_attempts: int = 1
    idempotent: bool = False
    justification: str = ""

    def __post_init__(self) -> None:
        if not 1 <= int(self.max_attempts) <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if self.max_attempts > 1 and not self.idempotent:
            raise ValueError("retry requires an idempotent capability")
        if self.max_attempts > 1 and not self.justification.strip():
            raise ValueError("retry requires an idempotency justification")


class ResilientCapabilityExecutor:
    """Routes capability calls with bounded, explicit, fail-closed retries."""

    def __init__(
        self,
        handlers: Mapping[str, Callable[[str, Dict[str, Any], GoalState], Any]],
        *,
        retry_policies: Mapping[str, CapabilityRetryPolicy] | None = None,
    ) -> None:
        self.handlers = {str(k): v for k, v in handlers.items()}
        if not self.handlers:
            raise ValueError("at least one handler is required")
        self.retry_policies = dict(retry_policies or {})
        unknown = set(self.retry_policies) - set(self.handlers)
        if unknown:
            raise ValueError(f"retry policy for unregistered capability: {sorted(unknown)}")

    @staticmethod
    def _coerce(raw: Any) -> ExecutionResult:
        if isinstance(raw, ExecutionResult):
            return raw
        if isinstance(raw, Mapping) and "status" in raw:
            status = str(raw.get("status", ""))
            if status not in {"ok", "failed", "blocked", "needs_approval"}:
                raise ValueError("handler returned invalid status")
            metadata = raw.get("metadata") or {}
            if not isinstance(metadata, Mapping):
                raise ValueError("handler metadata must be an object")
            return ExecutionResult(
                status=status,
                output=raw.get("output"),
                error=str(raw.get("error", "")),
                metadata=dict(metadata),
            )
        return ExecutionResult("ok", output=raw)

    @staticmethod
    def _is_transient(result: ExecutionResult) -> bool:
        if result.status != "failed":
            return False
        return bool(result.metadata.get("transient", False))

    def execute(self, action: PlannedAction, state: GoalState) -> ExecutionResult:
        handler = self.handlers.get(action.kind)
        if handler is None:
            return ExecutionResult("blocked", error=f"capability_not_registered:{action.kind}")

        policy = self.retry_policies.get(action.kind, CapabilityRetryPolicy())
        last = ExecutionResult("failed", error="capability_not_executed")
        for attempt in range(1, policy.max_attempts + 1):
            try:
                last = self._coerce(handler(action.instruction, dict(action.metadata), state))
            except Exception as exc:
                last = ExecutionResult(
                    "failed",
                    error=f"{type(exc).__name__}: {exc}",
                    metadata={"handler_exception": True, "kind": action.kind},
                )

            # Approval and blocking are terminal. Never replay them.
            if last.status in {"ok", "blocked", "needs_approval"}:
                break
            if not self._is_transient(last):
                break
            if attempt >= policy.max_attempts:
                break

        metadata = dict(last.metadata)
        metadata["attempts"] = attempt
        metadata["retry_safe"] = bool(policy.max_attempts > 1)
        return ExecutionResult(
            status=last.status,
            output=last.output,
            error=last.error,
            metadata=metadata,
        )
