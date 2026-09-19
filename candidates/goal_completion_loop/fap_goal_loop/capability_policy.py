from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping

from .goal_loop import GoalState
from .resilient import ResilientCapabilityHandler, RetryPolicy

CapabilityHandler = Callable[[str, Dict[str, Any], GoalState], Any]


@dataclass(frozen=True)
class CapabilityRegistration:
    """One capability plus an explicit local-retry safety contract.

    Retry is fail-closed: declaring a handler retry-safe is not enough; the
    registration must also state why repeated execution is idempotent or has
    no externally visible side effect.
    """

    name: str
    handler: CapabilityHandler
    retry_safe: bool = False
    idempotency_basis: str = ""
    max_attempts: int = 2
    retryable_errors: tuple[str, ...] = ("timeout", "temporarily_unavailable")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("capability name is required")
        if self.retry_safe and not self.idempotency_basis.strip():
            raise ValueError("retry-safe capability requires idempotency_basis")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")

    def effective_handler(self) -> CapabilityHandler:
        if not self.retry_safe or self.max_attempts == 1:
            return self.handler
        return ResilientCapabilityHandler(
            self.handler,
            policy=RetryPolicy(max_attempts=self.max_attempts),
            retryable_errors=self.retryable_errors,
        )


def build_capability_handlers(
    registrations: Iterable[CapabilityRegistration],
) -> Mapping[str, CapabilityHandler]:
    """Build a router map while rejecting duplicate capability names."""

    handlers: dict[str, CapabilityHandler] = {}
    for registration in registrations:
        name = registration.name.strip()
        if name in handlers:
            raise ValueError(f"duplicate capability registration: {name}")
        handlers[name] = registration.effective_handler()
    if not handlers:
        raise ValueError("at least one capability registration is required")
    return handlers
