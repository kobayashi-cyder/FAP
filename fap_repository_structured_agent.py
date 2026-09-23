from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

from fap_repository_agent import RepositoryCodingCoordinator, RepositoryCodingResult
from fap_repository_structured_patch import (
    RepositoryStructuredProposalProvider,
    StructuredRepairProvider,
    StructuredRepairSpecProvider,
    StructuredSpecInput,
)
from fap_repository_structured_planner import RepositoryStructuredPlanner
from fap_repository_test_selector import (
    RepositoryVerificationSelector,
    VerificationSelection,
)
from fap_repository_planner import PatchPlan
from fap_repository_reader import RepositoryReadContext


StructuredProposalSpecProvider = Callable[
    [PatchPlan, RepositoryReadContext],
    Iterable[StructuredSpecInput],
]


@dataclass(frozen=True)
class StructuredCodingRun:
    version: str
    goal: str
    state: str
    plan_id: str
    verification: VerificationSelection
    coding: RepositoryCodingResult
    errors: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryStructuredCodingAgent:
    """Integrated non-promoting repository coding pipeline.

    Flow:
      structured plan
        -> dependency-aware automatic test selection
        -> structured declarative edit compilation
        -> existing detached-worktree executor/verifier
        -> bounded structured repair
        -> verified candidate

    The agent deliberately exposes no automatic promotion method. A verified
    candidate remains separate from source/main until an explicit existing
    promotion workflow is invoked elsewhere.
    """

    VERSION = "fap.repository.structured_agent.v1"

    def __init__(
        self,
        root: str | Path,
        *,
        max_files: int = 12,
        max_source_bytes: int = 240_000,
        max_repairs: int = 2,
        max_operations: int = 24,
        max_focused_tests: int = 8,
        impact_depth: int = 2,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        self.planner = RepositoryStructuredPlanner(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
        )
        self.coordinator = RepositoryCodingCoordinator(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
            max_repairs=max_repairs,
            planner=self.planner,
        )
        self.selector = RepositoryVerificationSelector(
            self.root,
            max_focused_tests=max_focused_tests,
            impact_depth=impact_depth,
        )
        self.max_operations = int(max_operations)
        if not 1 <= self.max_operations <= 64:
            raise ValueError("max_operations must be in [1, 64]")

    def run(
        self,
        goal: str,
        provider: StructuredProposalSpecProvider,
        *,
        repair_provider: StructuredRepairSpecProvider | None = None,
    ) -> StructuredCodingRun:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        if not callable(provider):
            raise TypeError("provider must be callable")
        if repair_provider is not None and not callable(repair_provider):
            raise TypeError("repair_provider must be callable")

        plan = self.planner.plan(goal)
        verification = self.selector.select(plan)
        proposal = RepositoryStructuredProposalProvider(
            self.root,
            provider,
            max_operations=self.max_operations,
        )
        repairer = (
            StructuredRepairProvider(proposal, plan, repair_provider)
            if repair_provider is not None
            else None
        )
        coding = self.coordinator.run(
            goal,
            proposal,
            verification.commands,
            repairer=repairer,
        )

        errors: list[str] = list(coding.errors)
        if coding.plan.plan_id != plan.plan_id:
            errors.append("preflight_plan_changed")
        if verification.plan_id != plan.plan_id:
            errors.append("verification_plan_mismatch")
        state = (
            "verified_candidate"
            if coding.state == "verified_candidate" and not errors
            else "rejected"
        )

        return StructuredCodingRun(
            version=self.VERSION,
            goal=goal,
            state=state,
            plan_id=plan.plan_id,
            verification=verification,
            coding=coding,
            errors=tuple(dict.fromkeys(errors)),
        )
