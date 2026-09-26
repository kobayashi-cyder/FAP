from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from fap_repository_agent import (
    ProposalProvider,
    RepairProvider,
    RepositoryCodingResult,
)
from fap_repository_chat_bridge import ChatCodingRequest, RepositoryChatBridge
from fap_repository_chat_coding import RepositoryChatCodingCoordinator
from fap_repository_planner import PatchPlan
from fap_repository_test_selector import (
    RepositoryVerificationSelector,
    VerificationSelection,
)


AUTO_CODING_VERSION = "fap.repository.auto_coding.v1"


@dataclass(frozen=True)
class PreparedAutoCoding:
    version: str
    request: ChatCodingRequest
    plan: PatchPlan
    verification: VerificationSelection

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AutoCodingOutcome:
    version: str
    state: str
    prepared: PreparedAutoCoding
    result: RepositoryCodingResult | None
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryAutoCodingOrchestrator:
    """Compose chat coding, planning and automatic verification selection.

    This layer intentionally does not promote or merge anything. It turns a chat
    instruction into a bounded repository plan, derives verification commands
    from that exact plan, checks that repository context has not changed, then
    delegates execution to the existing detached-worktree coding coordinator.
    """

    VERSION = AUTO_CODING_VERSION

    def __init__(
        self,
        root: str | Path,
        *,
        chat: RepositoryChatCodingCoordinator | None = None,
        selector: RepositoryVerificationSelector | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.chat = chat or RepositoryChatCodingCoordinator(self.root)
        self.selector = selector or RepositoryVerificationSelector(self.root)

        coordinator_root = getattr(self.chat.coordinator, "root", self.root)
        if Path(coordinator_root).expanduser().resolve() != self.root:
            raise ValueError("chat coordinator root does not match orchestrator root")

    def prepare(
        self,
        current_text: str,
        *,
        history: Iterable[Mapping[str, object] | str] = (),
        branch: str,
        base_commit: str = "",
    ) -> PreparedAutoCoding:
        request = self.chat.prepare(
            current_text,
            history=history,
            branch=branch,
            base_commit=base_commit,
        )
        if request.contract != RepositoryChatBridge.CONTRACT:
            raise ValueError(
                f"unsupported chat coding contract: {request.contract}"
            )

        plan = self.chat.coordinator.planner.plan(
            request.goal,
            preferred_paths=request.file_hints,
        )
        verification = self.selector.select(plan)
        if verification.plan_id != plan.plan_id:
            raise ValueError("verification selection plan_id mismatch")

        return PreparedAutoCoding(
            version=self.VERSION,
            request=request,
            plan=plan,
            verification=verification,
        )

    def run(
        self,
        prepared: PreparedAutoCoding,
        proposer: ProposalProvider,
        *,
        repairer: RepairProvider | None = None,
    ) -> AutoCodingOutcome:
        self._validate_prepared(prepared)

        current = self.chat.coordinator.planner.reader.read(
            prepared.request.goal,
            preferred_paths=prepared.request.file_hints,
        )
        expected_digest = prepared.plan.task.repository_digest
        if current.repository_digest != expected_digest:
            return self._blocked(
                prepared,
                "auto_orchestrator:repository_context_changed_after_prepare",
            )

        result = self.chat.run(
            prepared.request,
            proposer,
            prepared.verification.commands,
            repairer=repairer,
        )

        errors: list[str] = []
        state = result.state

        if result.plan.plan_id != prepared.plan.plan_id:
            state = "rejected"
            errors.append("auto_orchestrator:plan_changed_during_run")

        if (
            result.plan.task.repository_digest
            != prepared.plan.task.repository_digest
        ):
            state = "rejected"
            errors.append("auto_orchestrator:repository_digest_changed_during_run")

        if state != "verified_candidate":
            errors.extend(str(value) for value in result.errors)

        return AutoCodingOutcome(
            version=self.VERSION,
            state=state,
            prepared=prepared,
            result=result,
            errors=tuple(dict.fromkeys(errors)),
        )

    def run_text(
        self,
        current_text: str,
        proposer: ProposalProvider,
        *,
        history: Iterable[Mapping[str, object] | str] = (),
        branch: str,
        base_commit: str = "",
        repairer: RepairProvider | None = None,
    ) -> AutoCodingOutcome:
        prepared = self.prepare(
            current_text,
            history=history,
            branch=branch,
            base_commit=base_commit,
        )
        return self.run(prepared, proposer, repairer=repairer)

    def _validate_prepared(self, prepared: PreparedAutoCoding) -> None:
        if prepared.version != self.VERSION:
            raise ValueError(
                f"unsupported auto coding version: {prepared.version}"
            )
        if prepared.request.contract != RepositoryChatBridge.CONTRACT:
            raise ValueError(
                f"unsupported chat coding contract: {prepared.request.contract}"
            )
        if prepared.request.branch in {"main", "master"}:
            raise ValueError("auto coding requires a non-main branch")
        if prepared.verification.plan_id != prepared.plan.plan_id:
            raise ValueError("verification selection plan_id mismatch")

    def _blocked(
        self,
        prepared: PreparedAutoCoding,
        error: str,
    ) -> AutoCodingOutcome:
        return AutoCodingOutcome(
            version=self.VERSION,
            state="blocked",
            prepared=prepared,
            result=None,
            errors=(error,),
        )
