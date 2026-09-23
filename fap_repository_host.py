from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Callable, Iterable

from fap_repository_agent import (
    ProposalProvider,
    RepairProvider,
    RepositoryCodingCoordinator,
)
from fap_repository_contracts import (
    HOST_CONTRACT,
    validate_contract_payload,
)
from fap_repository_verifier import VerificationCommand


_SAFE_REASON = re.compile(r"[^0-9A-Za-z_.:-]+")


@dataclass(frozen=True)
class RepositoryHostResponse:
    contract: str
    state: str
    observation: str
    plan_id: str
    repository_digest: str
    progress: float
    reason: str
    attempts: int
    repairs_used: int
    paths: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        validate_contract_payload("host_response", payload)
        return payload


class FAPRepositoryCodingHost:
    """Provider-neutral callable boundary for embedding FAP repository coding.

    This class does not import FCA and does not perform promotion. A host may
    adapt the returned mapping into another system's typed organ result.

    The injected proposal/repair providers are trusted host components. All
    repository writes produced by their declarative FileEdit outputs remain
    subject to the V87.66-V87.70 planner/worktree/verifier boundaries.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        proposer: ProposalProvider,
        commands: Iterable[VerificationCommand],
        repairer: RepairProvider | None = None,
        coordinator: RepositoryCodingCoordinator | None = None,
        max_goal_chars: int = 20_000,
        verified_progress: float = 1.0,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.root}")
        if not callable(proposer):
            raise TypeError("proposer must be callable")
        if repairer is not None and not callable(repairer):
            raise TypeError("repairer must be callable")
        if not 256 <= int(max_goal_chars) <= 100_000:
            raise ValueError("max_goal_chars must be in [256, 100000]")
        if not 0.0 <= float(verified_progress) <= 1.0:
            raise ValueError("verified_progress must be in [0, 1]")

        self.proposer = proposer
        self.commands = tuple(commands)
        self.repairer = repairer
        self.max_goal_chars = int(max_goal_chars)
        self.verified_progress = float(verified_progress)
        self.coordinator = coordinator or RepositoryCodingCoordinator(self.root)
        if self.coordinator.root != self.root:
            raise ValueError("coordinator root does not match host root")

    def __call__(
        self,
        goal: str,
        observation: str = "",
        *,
        preferred_paths: tuple[str, ...] = (),
    ) -> RepositoryHostResponse:
        goal = str(goal or "").strip()
        if not goal:
            return self._blocked("empty_goal")
        if len(goal) > self.max_goal_chars:
            return self._blocked("goal_too_large")

        try:
            result = self.coordinator.run(
                goal,
                self.proposer,
                self.commands,
                repairer=self.repairer,
                preferred_paths=preferred_paths,
            )
        except Exception as exc:
            return self._blocked(f"repository_host_failed:{type(exc).__name__}")

        plan_id = result.plan.plan_id
        repository_digest = result.plan.task.repository_digest
        paths = tuple(dict.fromkeys(
            item.path for item in result.plan.files
            if item.operation in {"modify", "create", "delete"}
        ))[:32]
        if not paths:
            paths = tuple(dict.fromkeys(item.path for item in result.plan.files))[:32]
        if result.state == "verified_candidate" and result.repair is not None:
            return RepositoryHostResponse(
                contract=HOST_CONTRACT,
                state="verified_candidate",
                observation=(
                    "repository candidate verified "
                    f"plan={plan_id[:16]} "
                    f"attempts={len(result.repair.attempts)} "
                    f"repairs={result.repair.repairs_used} "
                    f"files={len(result.final_edits)}"
                ),
                plan_id=plan_id,
                repository_digest=repository_digest,
                progress=self.verified_progress,
                reason="repository_coding_verified_candidate",
                attempts=len(result.repair.attempts),
                repairs_used=result.repair.repairs_used,
                paths=paths,
            )

        attempts = len(result.repair.attempts) if result.repair is not None else 0
        repairs_used = result.repair.repairs_used if result.repair is not None else 0
        return RepositoryHostResponse(
            contract=HOST_CONTRACT,
            state="rejected",
            observation=(
                "repository coding rejected "
                f"plan={plan_id[:16]} attempts={attempts}"
            ),
            plan_id=plan_id,
            repository_digest=repository_digest,
            progress=0.0,
            reason=_reason_code(result.errors),
            attempts=attempts,
            repairs_used=repairs_used,
            paths=paths,
        )

    @staticmethod
    def _blocked(reason: str) -> RepositoryHostResponse:
        return RepositoryHostResponse(
            contract=HOST_CONTRACT,
            state="blocked",
            observation="repository coding blocked",
            plan_id="",
            repository_digest="",
            progress=0.0,
            reason=reason,
            attempts=0,
            repairs_used=0,
            paths=(),
        )


def _reason_code(errors: tuple[str, ...]) -> str:
    if not errors:
        return "repository_coding_rejected"
    raw = str(errors[0])
    # Keep the category and exception type, but drop arbitrary provider/error
    # message text that may contain local paths or secrets.
    pieces = raw.split(":")
    raw = ":".join(pieces[:2]) if len(pieces) >= 2 else pieces[0]
    cleaned = _SAFE_REASON.sub("_", raw).strip("_:")
    return cleaned[:160] or "repository_coding_rejected"
