from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

from fap_repository_contracts import CODING_RESULT_VERSION
from fap_repository_executor import FileEdit, RepositoryPatchExecutor
from fap_repository_planner import PatchPlan, RepositoryPlanner
from fap_repository_promotion import (
    PromotionApproval,
    PromotionReport,
    VerifiedCandidatePromoter,
)
from fap_repository_reader import RepositoryReadContext
from fap_repository_verifier import (
    BoundedRepairLoop,
    CandidateAttempt,
    RepairRunReport,
    RepositoryVerifier,
    VerificationCommand,
)


ProposalProvider = Callable[
    [PatchPlan, RepositoryReadContext],
    Iterable[FileEdit],
]

RepairProvider = Callable[
    [tuple[FileEdit, ...], CandidateAttempt],
    Iterable[FileEdit] | None,
]


@dataclass(frozen=True)
class RepositoryCodingResult:
    version: str
    goal: str
    state: str
    plan: PatchPlan
    context: RepositoryReadContext
    repair: RepairRunReport | None
    final_edits: tuple[FileEdit, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryCodingCoordinator:
    """V87.70 end-to-end coordinator for repository coding candidates.

    Flow:
      read -> plan -> proposal provider -> sandbox apply -> verify
           -> bounded repair -> verified candidate

    The coordinator itself never writes the source working tree and never
    creates a branch automatically. Promotion is a separate explicit method
    that delegates to the V87.69 gate.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        max_files: int = 8,
        max_source_bytes: int = 120_000,
        max_repairs: int = 2,
        planner: RepositoryPlanner | None = None,
        executor: RepositoryPatchExecutor | None = None,
        verifier: RepositoryVerifier | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.planner = planner or RepositoryPlanner(
            self.root,
            max_files=max_files,
            max_source_bytes=max_source_bytes,
        )
        self.executor = executor or RepositoryPatchExecutor(
            self.root,
            max_files=max_files,
        )
        self.verifier = verifier or RepositoryVerifier()
        self.max_repairs = int(max_repairs)
        if not 0 <= self.max_repairs <= 4:
            raise ValueError("max_repairs must be in [0, 4]")
        if self.planner.root != self.root:
            raise ValueError("planner root does not match coordinator root")
        if self.executor.root != self.root:
            raise ValueError("executor root does not match coordinator root")

    def run(
        self,
        goal: str,
        proposer: ProposalProvider,
        commands: Iterable[VerificationCommand],
        *,
        repairer: RepairProvider | None = None,
        preferred_paths: tuple[str, ...] = (),
    ) -> RepositoryCodingResult:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")

        plan = self.planner.plan(goal, preferred_paths=preferred_paths)
        context = self.planner.reader.read(goal, preferred_paths=preferred_paths)
        if context.repository_digest != plan.task.repository_digest:
            return self._reject(
                goal,
                plan,
                context,
                None,
                (),
                ("planner_context_digest_mismatch",),
            )
        if plan.status != "ready":
            return self._reject(
                goal,
                plan,
                context,
                None,
                (),
                (f"plan_not_ready:{plan.status}",),
            )

        try:
            initial_edits = tuple(proposer(plan, context))
        except Exception as exc:
            return self._reject(
                goal,
                plan,
                context,
                None,
                (),
                (f"proposal_provider_failed:{type(exc).__name__}:{exc}",),
            )
        if not initial_edits:
            return self._reject(
                goal,
                plan,
                context,
                None,
                (),
                ("proposal_provider_returned_no_edits",),
            )

        latest_edits = initial_edits

        def tracked_repairer(
            current: tuple[FileEdit, ...],
            attempt: CandidateAttempt,
        ) -> Iterable[FileEdit] | None:
            nonlocal latest_edits
            if repairer is None:
                return None
            proposal = repairer(current, attempt)
            if proposal is None:
                return None
            next_edits = tuple(proposal)
            if not next_edits:
                return ()
            latest_edits = next_edits
            return next_edits

        loop = BoundedRepairLoop(
            self.executor,
            self.verifier,
            max_repairs=self.max_repairs,
        )
        command_tuple = tuple(commands)
        try:
            repair = loop.run(
                plan,
                initial_edits,
                command_tuple,
                repairer=tracked_repairer if repairer is not None else None,
            )
        except Exception as exc:
            return self._reject(
                goal,
                plan,
                context,
                None,
                latest_edits,
                (f"execution_pipeline_failed:{type(exc).__name__}:{exc}",),
            )
        state = (
            "verified_candidate"
            if repair.state == "verified_candidate"
            else "rejected"
        )
        errors = () if state == "verified_candidate" else tuple(repair.errors)
        return RepositoryCodingResult(
            version=CODING_RESULT_VERSION,
            goal=goal,
            state=state,
            plan=plan,
            context=context,
            repair=repair,
            final_edits=latest_edits,
            errors=errors,
        )

    def promote_verified(
        self,
        result: RepositoryCodingResult,
        commands: Iterable[VerificationCommand],
        approval: PromotionApproval,
    ) -> PromotionReport:
        if result.version != CODING_RESULT_VERSION:
            raise ValueError(f"unsupported coding result version: {result.version}")
        if result.state != "verified_candidate" or result.repair is None:
            return PromotionReport(
                version="fap.repository.promotion.v1",
                plan_id=result.plan.plan_id,
                state="rejected",
                base_commit="",
                branch=None,
                commit_sha=None,
                verification=None,
                errors=("coding_result_not_verified",),
            )
        if result.repair.state != "verified_candidate":
            return PromotionReport(
                version="fap.repository.promotion.v1",
                plan_id=result.plan.plan_id,
                state="rejected",
                base_commit="",
                branch=None,
                commit_sha=None,
                verification=None,
                errors=("repair_evidence_not_verified",),
            )
        promoter = VerifiedCandidatePromoter(
            self.root,
            executor=self.executor,
            verifier=self.verifier,
        )
        return promoter.promote(
            result.plan,
            result.final_edits,
            tuple(commands),
            approval,
        )

    @staticmethod
    def _reject(
        goal: str,
        plan: PatchPlan,
        context: RepositoryReadContext,
        repair: RepairRunReport | None,
        final_edits: tuple[FileEdit, ...],
        errors: tuple[str, ...],
    ) -> RepositoryCodingResult:
        return RepositoryCodingResult(
            version=CODING_RESULT_VERSION,
            goal=goal,
            state="rejected",
            plan=plan,
            context=context,
            repair=repair,
            final_edits=final_edits,
            errors=errors,
        )
