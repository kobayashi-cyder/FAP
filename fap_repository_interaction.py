from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Callable, Iterable

from fap_interaction_fabric import (
    InteractionBudget,
    InteractionEndpoint,
    InteractionRequest,
)
from fap_repository_agent import (
    ProposalProvider,
    RepairProvider,
    RepositoryCodingCoordinator,
)
from fap_repository_host import FAPRepositoryCodingHost
from fap_repository_session import RepositorySessionLedger
from fap_repository_structured_planner import RepositoryStructuredPlanner
from fap_repository_verifier import VerificationCommand


IntentScorer = Callable[[InteractionRequest], float]


class RepositoryCodingInteraction:
    """Adaptive repository-coding endpoint for the generalized interaction fabric.

    The scorer is injected by the host so this module contains no language- or
    topic-specific routing branches. Exponential-linear budgets determine
    repository context breadth and bounded repair depth for each request.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        proposer: ProposalProvider,
        commands: Iterable[VerificationCommand],
        scorer: IntentScorer | None = None,
        repairer: RepairProvider | None = None,
        endpoint_id: str = "repository_coding",
        priority: float = 2.0,
        cost: float = 2.0,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.root}")
        if not callable(proposer):
            raise TypeError("proposer must be callable")
        if scorer is not None and not callable(scorer):
            raise TypeError("scorer must be callable or None")
        if repairer is not None and not callable(repairer):
            raise TypeError("repairer must be callable")

        self.proposer = proposer
        self.commands = tuple(commands)
        self.scorer = scorer or (lambda request: 0.0)
        self.repairer = repairer
        self.endpoint_id = endpoint_id
        self.priority = float(priority)
        self.cost = float(cost)
        self.repository_sessions = RepositorySessionLedger(
            max_sessions=128,
            max_paths=32,
        )

    def endpoint(self) -> InteractionEndpoint:
        return InteractionEndpoint(
            endpoint_id=self.endpoint_id,
            channels=("chat", "coding"),
            probe=self.scorer,
            handler=self._handle,
            priority=self.priority,
            cost=self.cost,
        )

    def _handle(
        self,
        request: InteractionRequest,
        budget: InteractionBudget,
    ) -> dict:
        max_files = min(32, max(4, int(budget.route_candidates)))
        max_source_bytes = min(
            1_000_000,
            max(60_000, int(budget.source_bytes)),
        )
        max_repairs = min(4, max(0, int(budget.repair_rounds)))

        planner = RepositoryStructuredPlanner(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
        )
        coordinator = RepositoryCodingCoordinator(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
            max_repairs=max_repairs,
            planner=planner,
        )
        session_id = self._session_id(request)
        repository_digest = coordinator.planner.reader.repository_digest
        preferred_paths = (
            self.repository_sessions.preferred_paths(session_id, repository_digest)
            if session_id else ()
        )

        host = FAPRepositoryCodingHost(
            self.root,
            proposer=self.proposer,
            commands=self.commands,
            repairer=self.repairer,
            coordinator=coordinator,
            max_goal_chars=min(100_000, max(256, int(budget.context_chars))),
        )

        observation = self._observation(request, budget)
        response = host(
            request.text,
            observation,
            preferred_paths=preferred_paths,
        )
        if session_id and response.repository_digest and response.plan_id:
            self.repository_sessions.record(
                session_id,
                response.repository_digest,
                response.plan_id,
                state=response.state,
                paths=response.paths,
            )
        session_snapshot = (
            self.repository_sessions.snapshot(session_id)
            if session_id else None
        )
        data = response.to_dict()
        return {
            "ok": response.state == "verified_candidate",
            "reply": response.observation,
            "confidence": 0.99 if response.state == "verified_candidate" else 0.60,
            "local": True,
            "repository_coding": data,
            "route_tags": [
                "interaction-fabric",
                "repository-coding",
                "exponential-linear-budget",
                response.state,
            ],
            "repository_session_continuity": {
                "enabled": bool(session_id),
                "session_id": session_id or "",
                "preferred_paths_used": list(preferred_paths),
                "remembered_paths": list(session_snapshot.paths) if session_snapshot else [],
                "stores_source_text": False,
            },
            "adaptive_repository_budget": {
                "max_files": max_files,
                "max_source_bytes": max_source_bytes,
                "max_repairs": max_repairs,
                "scale": budget.scale,
                "demand": budget.demand,
            },
        }

    @staticmethod
    def _session_id(request: InteractionRequest) -> str:
        metadata = request.metadata
        if not isinstance(metadata, Mapping):
            return ""
        candidates = []
        direct = metadata.get("session_id")
        if isinstance(direct, str):
            candidates.append(direct)
        continuity = metadata.get("session_continuity")
        if isinstance(continuity, Mapping):
            nested = continuity.get("session_id")
            if isinstance(nested, str):
                candidates.append(nested)
        for raw in candidates:
            value = raw.strip()
            if value and len(value) <= 128 and all(
                ch.isalnum() or ch in "_.:-" for ch in value
            ):
                return value
        return ""

    @staticmethod
    def _observation(
        request: InteractionRequest,
        budget: InteractionBudget,
    ) -> str:
        if not request.history:
            return ""
        latest = request.history[-1]
        value = ""
        if isinstance(latest, Mapping):
            for key in ("content", "text", "reply", "observation"):
                raw = latest.get(key)
                if isinstance(raw, str) and raw.strip():
                    value = raw.strip()
                    break
        if not value:
            return ""
        limit = min(8_000, max(512, int(budget.context_chars // 8)))
        return value[:limit]
