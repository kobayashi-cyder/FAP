from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Callable, Iterable

from fap_repository_contracts import (
    CODING_RESULT_VERSION,
    validate_contract_payload,
)
from fap_repository_executor import FileEdit, RepositoryPatchExecutor
from fap_repository_plan_quality import RepositoryPlanQualityGate
from fap_repository_planner import PatchPlan, RepositoryPlanner
from fap_repository_promotion import (
    PromotionApproval,
    PromotionReport,
    VerifiedCandidatePromoter,
)
from fap_repository_reader import RepositoryReadContext
from fap_repository_repair_guard import GuardedRepairProvider
from fap_repository_security_policy import RepositorySecurityPolicy
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
        payload = asdict(self)
        validate_contract_payload("coding_result", payload)
        return payload


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
        security_policy: RepositorySecurityPolicy | None = None,
        plan_quality_gate: RepositoryPlanQualityGate | None = None,
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
        self.plan_quality_gate = plan_quality_gate or RepositoryPlanQualityGate(
            max_files=max_files,
        )
        self.security_policy = security_policy or RepositorySecurityPolicy(
            allowed_executables=self.verifier.allowed_executables,
            allowed_executable_paths=(sys.executable,),
            max_files=max_files,
            max_commands=self.verifier.max_commands,
            max_timeout_sec=self.verifier.max_timeout_sec,
        )
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

        quality = self.plan_quality_gate.assess(plan)
        if not quality.acceptable:
            return self._reject(
                goal,
                plan,
                context,
                None,
                (),
                _plan_quality_errors(quality),
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

        command_tuple = tuple(commands)
        preflight = self.security_policy.audit(
            plan=plan,
            edits=initial_edits,
            commands=command_tuple,
        )
        if not preflight.allowed:
            return self._reject(
                goal,
                plan,
                context,
                None,
                initial_edits,
                _security_errors(preflight),
            )

        latest_edits = initial_edits
        repair_security_errors: tuple[str, ...] = ()
        guarded_repairer: GuardedRepairProvider | None = None
        if repairer is not None:
            guarded_repairer = GuardedRepairProvider(
                repairer,
                max_seen=max(4, (self.max_repairs + 1) * 2),
            )

        def tracked_repairer(
            current: tuple[FileEdit, ...],
            attempt: CandidateAttempt,
        ) -> Iterable[FileEdit] | None:
            nonlocal latest_edits, repair_security_errors
            if guarded_repairer is None:
                return None
            proposal = guarded_repairer(current, attempt)
            if proposal is None:
                return None
            next_edits = tuple(proposal)
            if not next_edits:
                return ()
            repair_preflight = self.security_policy.audit(
                plan=plan,
                edits=next_edits,
                commands=command_tuple,
            )
            if not repair_preflight.allowed:
                repair_security_errors = _security_errors(repair_preflight)
                return ()
            latest_edits = next_edits
            return next_edits

        loop = BoundedRepairLoop(
            self.executor,
            self.verifier,
            max_repairs=self.max_repairs,
        )
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
        if state != "verified_candidate" and repair_security_errors:
            errors = tuple(dict.fromkeys(errors + repair_security_errors))
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


def _security_errors(report) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            f"security_policy:{finding.code}"
            for finding in report.findings
            if finding.severity == "fatal"
        )
    )


def _plan_quality_errors(report) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            f"plan_quality:{issue.code}"
            for issue in report.issues
            if issue.severity == "fatal"
        )
    )
