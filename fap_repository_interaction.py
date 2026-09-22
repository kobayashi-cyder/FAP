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
        scorer: IntentScorer,
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
        if not callable(scorer):
            raise TypeError("scorer must be callable")
        if repairer is not None and not callable(repairer):
            raise TypeError("repairer must be callable")

        self.proposer = proposer
        self.commands = tuple(commands)
        self.scorer = scorer
        self.repairer = repairer
        self.endpoint_id = endpoint_id
        self.priority = float(priority)
        self.cost = float(cost)

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

        coordinator = RepositoryCodingCoordinator(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
            max_repairs=max_repairs,
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
        response = host(request.text, observation)
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
            "adaptive_repository_budget": {
                "max_files": max_files,
                "max_source_bytes": max_source_bytes,
                "max_repairs": max_repairs,
                "scale": budget.scale,
                "demand": budget.demand,
            },
        }

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
