from __future__ import annotations

from dataclasses import asdict, dataclass

from fap_repository_planner import PatchPlan


@dataclass(frozen=True)
class PlanQualityIssue:
    code: str
    severity: str
    path: str = ""


@dataclass(frozen=True)
class PlanQualityReport:
    version: str
    plan_id: str
    acceptable: bool
    mutation_count: int
    inspect_count: int
    issues: tuple[PlanQualityIssue, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryPlanQualityGate:
    """Deterministic quality gate over a produced PatchPlan.

    This does not replace planning. It validates execution-relevant invariants
    before a proposal provider spends tokens/time generating edits.
    """

    VERSION = "fap.repository.plan_quality.v1"

    def assess(self, plan: PatchPlan) -> PlanQualityReport:
        issues: list[PlanQualityIssue] = []
        seen: set[str] = set()
        mutations = 0
        inspections = 0

        if plan.status != "ready":
            issues.append(PlanQualityIssue("plan_not_ready", "fatal"))

        for item in plan.files:
            if item.path in seen:
                issues.append(PlanQualityIssue("duplicate_path", "fatal", item.path))
            seen.add(item.path)

            if item.operation == "inspect":
                inspections += 1
                continue
            if item.operation not in {"modify", "create", "delete"}:
                issues.append(
                    PlanQualityIssue("unsupported_operation", "fatal", item.path)
                )
                continue
            mutations += 1

            if item.operation == "create":
                if item.before_sha256:
                    issues.append(
                        PlanQualityIssue("create_has_before_hash", "fatal", item.path)
                    )
            else:
                if not item.before_sha256:
                    issues.append(
                        PlanQualityIssue("mutation_missing_before_hash", "fatal", item.path)
                    )

        checks = set(plan.required_checks)
        if mutations:
            if "sha_precondition" not in checks:
                issues.append(PlanQualityIssue("missing_sha_precondition", "fatal"))
            if "sandbox_only" not in checks:
                issues.append(PlanQualityIssue("missing_sandbox_only", "fatal"))
            if "no_direct_main_write" not in checks:
                issues.append(PlanQualityIssue("missing_no_direct_main_write", "fatal"))
            if "regression_tests" not in checks:
                issues.append(PlanQualityIssue("missing_regression_tests", "fatal"))
        else:
            issues.append(PlanQualityIssue("no_mutation_targets", "warning"))

        if len(plan.files) > 8:
            issues.append(PlanQualityIssue("broad_plan", "warning"))
        if any(flag == "stale_context" for flag in plan.risk_flags):
            issues.append(PlanQualityIssue("stale_context_risk", "fatal"))

        acceptable = not any(issue.severity == "fatal" for issue in issues)
        return PlanQualityReport(
            version=self.VERSION,
            plan_id=plan.plan_id,
            acceptable=acceptable,
            mutation_count=mutations,
            inspect_count=inspections,
            issues=tuple(issues),
        )
