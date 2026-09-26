from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from fap_repository_agent import (
    ProposalProvider,
    RepairProvider,
    RepositoryCodingCoordinator,
    RepositoryCodingResult,
)
from fap_repository_chat_bridge import ChatCodingRequest, RepositoryChatBridge
from fap_repository_verifier import VerificationCommand


class RepositoryChatCodingCoordinator:
    """Bounded chat-to-coding adapter for the repository coding pipeline."""

    def __init__(
        self,
        root: str | Path,
        *,
        coordinator: RepositoryCodingCoordinator | None = None,
        bridge: RepositoryChatBridge | None = None,
    ) -> None:
        self.coordinator = coordinator or RepositoryCodingCoordinator(root)
        self.bridge = bridge or RepositoryChatBridge()

    def prepare(
        self,
        current_text: str,
        *,
        history: Iterable[Mapping[str, object] | str] = (),
        branch: str,
        base_commit: str = "",
    ) -> ChatCodingRequest:
        return self.bridge.build(
            current_text,
            history=history,
            branch=branch,
            base_commit=base_commit,
        )

    def run(
        self,
        request: ChatCodingRequest,
        proposer: ProposalProvider,
        commands: Iterable[VerificationCommand],
        *,
        repairer: RepairProvider | None = None,
    ) -> RepositoryCodingResult:
        if request.contract != RepositoryChatBridge.CONTRACT:
            raise ValueError(f"unsupported chat coding contract: {request.contract}")
        if request.branch in {"main", "master"}:
            raise ValueError("chat coding requests require a non-main branch")
        return self.coordinator.run(
            request.goal,
            proposer,
            commands,
            repairer=repairer,
            preferred_paths=request.file_hints,
        )
